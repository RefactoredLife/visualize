#! /Library/Frameworks/Python.framework/Versions/3.6/bin/python3

import signal
import gspread
import os
import string
from oauth2client.service_account import ServiceAccountCredentials
import json
import pandas as pd
import imaplib, email
from datetime import datetime, timedelta
import re
from bs4 import BeautifulSoup
import quopri
import requests
import base64
import pytz
import time
from sqlalchemy import create_engine, text
from app.common.config import (
    GMAIL_USER,
    GMAIL_PASSWORD,
    GMAIL_IMAP_SERVER,
    GOOGLE_PORTFOLIO_WORKSHEET,
    MARIADB_DATABASE,
    MARIADB_HOST,
    MARIADB_PASSWORD,
    MARIADB_PORT,
    MARIADB_USER,
)
from app.common.utils import log_runtime


class Gmail:

    @log_runtime
    def __init__(self):
        #self.cat_df = pd.read_csv("statements/csv/merchant-category.csv")
        #self.cat_df = self.cat_df.set_index('merchant')
        self.subjects = ['A charge was authorized for your Fidelity® card',
                         'A card on your account was not present',
                         'transaction was made on your Citi',
                         'Fidelity Alerts - Direct Debit Withdrawal',
                         'has shipped',
                         'Fidelity Alerts: Order Partially',
                         'Fidelity Alerts: Order Execution',
                         'Online Account Transfer Initiated',
                         'Refund on order',
                         'Your refund for',
                         'Your Citi Double Cash account has been credited',
                         'Wells Fargo direct deposit is available',
                         'Wells Fargo account update',
                         'Confirmation of payment on the Citi® Double Cash account',
                         'Fidelity Alerts: Deposit Received',
                         'Fidelity Investments Credit Card Payment Posted',
                         'Shipped: Now arriving early',
                         'Fidelity Investments Credit Card Transaction Notification']
        self.df = self._get_expenses()

    def exit_data(self):
        print("Exiting")

        # sys.exit()
        os.kill(os.getpid(), signal.SIGTERM)

    def process_emails(self):

        rows = []
        msg_count = 0
        date_30_days_ago = (datetime.now() - timedelta(days=30)).strftime("%d-%b-%Y")
        #result, data = con.uid('search', None, f'(SINCE {date_30_days_ago})')
        result, data = con.uid('search', None, "UNSEEN")  # search and return uids instead
        # result, data = con.search(None, 'FROM', 'Fidelity.Investments@mail.fidelity.com')
        # result, data = con.search(None, 'FROM', 'Fidelity.Alerts@fidelity.com')
        # result, data = con.search(None, 'SUBJECT', 'Fidelity Alerts: Order Execution')
        # latest_email_uid = data[0].split()[-1]

        latest_email_uids = data[0].split()
        for latest_email_uid in latest_email_uids:
            msg_count = msg_count + 1
            # print(msg_count)

            sender, receiver, date, subject, body = self.get_email_data(latest_email_uid)

            if sender is None:
                continue

            if 'wellsfargo.com' in sender:
                theDate = datetime.strptime(date, '%a, %d %b %Y %H:%M:%S %z (PDT)')
                rows = self.process_wells(msg_count, rows, body, theDate, subject)
            elif 'citi.com' in sender:
                if 'A card on your account was not present' in subject:
                    rows = self.process_citi_card_not_present(msg_count, rows, body, subject)
                else:
                    rows = self.process_citi_body(msg_count, rows, body)
            elif 'fidelityealerts@alert.fidelityrewards.com' in sender:
                #theDate = datetime.strptime(date, '%d %b %Y %H:%M:%S %z')
                theDate = datetime.strptime(date, '%a, %d %b %Y %H:%M:%S %z (UTC)')
                rows = self.process_fidelity_card(msg_count, rows, body, theDate, subject)
            else:
                try:
                    theDate = datetime.strptime(date, '%a, %d %b %Y %H:%M:%S %z')
                except:
                    theDate = datetime.strptime(date, '%a, %d %b %Y %H:%M:%S %Z')
                if 'amazon.com' in sender and 'has shipped' in subject:
                    rows = self.process_amazon_body(msg_count, rows, body, theDate, subject)
                elif 'amazon.com' in sender and 'efund' in subject:
                    rows = self.process_amazon_refund(msg_count, rows, body, theDate, subject)
                else:
                    #continue
                    rows = self.process_fidelity_other(msg_count, rows, body, theDate)
        return rows

    def get_email_data(self, latest_email_uid):

        result, data = con.uid('fetch', latest_email_uid, '(BODY.PEEK[HEADER])')

        if result not in 'OK':
            return None, None, None, None, None

        email_message, formatted_date, received_date, receiver, sender, subject = self.parse_header(data)

        body = ""

        #if any(re.findall(r'|'.join(self.subjects), subject, re.IGNORECASE)):
        if subject.startswith('A charge was authorized for your'):
            print('{} {} {} (Processed)'.format(formatted_date.strftime('%m/%d/%Y %H:%M:%S'), sender, subject))
            result, data = con.uid('fetch', latest_email_uid, '(RFC822)')
            email_message, formatted_date, received_date, receiver, sender, subject = self.parse_header(data)
            body = self.get_content(email_message, 'text/html')
            if body is None:
                body = self.get_content(email_message, 'text/plain')
            return sender, receiver, received_date, subject, body
        elif subject.startswith('Delivered:'):
            result, data = con.uid('fetch', latest_email_uid, '(RFC822)')
            return None, None, None, None, None
        elif subject.startswith('Your Amazon.com order') and not subject.endswith('has shipped'):
            result, data = con.uid('fetch', latest_email_uid, '(RFC822)')
            return None, None, None, None, None
        else:
            print('{} {} {} (Ignored)'.format(formatted_date.strftime('%m/%d/%Y %H:%M:%S'), sender, subject))
            return None, None, None, None, None

    def parse_header(self, data):
        raw_email = data[0][1]
        email_message = email.message_from_bytes(raw_email)
        # email_message = email.message_from_string(raw_email)
        sender = email.utils.parseaddr(email_message['From'])[1]
        receiver = email_message['To'][1]
        received_date = email_message['Date']
        date_tuple = email.utils.parsedate_tz(received_date)
        if date_tuple:
            formatted_date = datetime.fromtimestamp(email.utils.mktime_tz(date_tuple))
        if 'citi.com' in sender:
            subject = email_message['Subject'].replace('=?utf-8?B?', '').replace('?', '').replace('\r\n', '')
            try:
                subject = base64.b64decode(subject).decode('utf-8')
            except:
                pass
        else:
            subject = email_message['Subject']
        return email_message, formatted_date, received_date, receiver, sender, subject

    def get_content(self, email_message, content_type):
        for part in email_message.walk():
            if part.get_content_type() == content_type:
                body = part.get_payload(decode=True)
                return body
        return None

    def process_fidelity_other(self, msg_count, rows, body, theDate):
        lines = quopri.decodestring(body)
        soup = BeautifulSoup(lines, "lxml")
        tables = soup.find_all("tbody")
        if len(tables) == 0:
            tables = soup.find_all("table")

        for i in range(0, len(tables)):
            storeTable = tables[i].find_all("td")
            for td in storeTable:
                tdText = td.text.replace('\r\n', '').replace('=0A', '\n').replace('=', '')
                if tdText.startswith('Account:'):
                    continue
                    #self.process_orders(msg_count, rows, tdText, theDate)
                elif 'If you authorized this transaction' in tdText:
                    self.process_debits(msg_count, rows, tdText, theDate)
                    return rows
                elif 'A transfer from the above referenced account' in tdText:
                    self.process_transfer(msg_count, rows, tdText, theDate)
                    return rows
        return rows

    def process_fidelity_card(self, msg_count, rows, body, theDate, subject):
        lines = quopri.decodestring(body)
        soup = BeautifulSoup(lines, "lxml")
        tables = soup.find_all("tbody")
        if len(tables) == 0:
            tables = soup.find_all("table")

        # for i in range(0, len(tables)):
        storeTable = tables[0].find_all("td")
        # for td in storeTable:
        if 'Credit Card Payment Posted' in subject:
            tdText = storeTable[2].text.replace('\r\n', '').replace('=0A', '\n').replace('=', '')
            body_re = re.match(
                '(.*)A payment of \$((\d{1,3},?)*\d{1,3}\.\d+) has been posted to your account on (.*). To view your account(.*)',
                tdText.replace('\n', ''))
            merchant = 'Payment'
            txnType = 'Payment'
            amount = round(float(body_re.group(2).replace(',', '')), 2)
        else:
            tdText = storeTable[5].text.replace('\r\n', '').replace('=0A', '\n').replace('=', '')
            body_re = re.match('(.*) charged \$((\d{1,3},?)*\d{1,3}\.\d+) at (.*).Your(.*)',
                               tdText.replace('\n', ''))
            merchant = body_re.group(4)
            txnType = 'Withdrawl'
            amount = round(float(body_re.group(2).replace(',', '')) * -1, 2)
        # tables = soup.find_all("span", class_="TS-ActionSummaryV2-Value")
        account = 'FidelityVisa'
        txnDate = theDate.strftime("%-m/%-d/%Y")
        pacific_time = theDate - timedelta(hours=2)
        txnTime = pacific_time.strftime("%H:%M:%S")
        if 'Credit Card Payment Posted' in subject:
            rows.append(
                [txnTime, 'Money Market', txnDate, 'Fidelity Visa Payment', None, amount * -1, 'Withdrawl', None, None,
                 None, None, None #self.get_category(merchant)
                ])

        rows.append([txnDate, merchant, amount, account])
        return rows

    def process_amazon_refund(self, msg_count, rows, body, emailReceived, subject):
        lines = quopri.decodestring(body).decode('latin-1')
        if 'Refund on order' in subject:
            content_re = re.match('(.*)\\$(\d+\.\d+)', lines.split('\r\n')[2])
            amount = content_re.group(2)
            subject_re = re.match('Refund on order (.*)', subject)
            item = 'Order {}'.format(subject_re.group(1))
        else:
            soup = BeautifulSoup(lines, "lxml")
            table = soup.find('table', id="refundDetails")
            td = table.find_all('td')
            amount = td[0].find_all('span')[1].text[1:].replace('*', '')
            sub = re.match('Your refund for (.*).', subject)
            item = sub.group(1)
        txnDate = emailReceived.strftime("%-m/%-d/%Y")
        txnTime = emailReceived.strftime("%I:%M %p")
        rows.append([txnTime, 'Chase', txnDate, item, None,
                     round(float(amount.replace(',', '')), 2), 'Return', None, None, None,
                     None, None #self.get_category(item)
                    ])
        return rows

    def process_amazon_body(self, msg_count, rows, body, emailReceived, subject):
        lines = quopri.decodestring(body).decode('latin-1')
        soup = BeautifulSoup(lines, "lxml")
        amount = soup.find_all("div", class_="informationText")[2].text.strip()[1:]
        sre = re.match('Your (.*) has shipped', subject)
        merchant = sre.group(1)
        category = self.get_category(merchant)
        if 'Rewards points applied' in lines:
            merchant = '{} (Rewards)'.format(merchant)
        # print('Amazon: {}'.format(emailReceived))
        txnDate = emailReceived.strftime("%-m/%-d/%Y")
        txnTime = emailReceived.strftime("%I:%M %p")
        rows.append([txnTime, 'Chase', txnDate, merchant, None,
                     round(float(amount.replace(',', '')) * -1, 2), 'Sale', None, None, None,
                     None, category])
        return rows

    def process_wells(self, msg_count, rows, body, emailReceived, subject):
        soup = BeautifulSoup(body, "lxml")
        tables = soup.find_all("table")
        tablerows = tables[1].find_all('tr')
        transaction = tablerows[1].find_all('td')
        merchant = transaction[0].text
        amount = transaction[1].text.strip()[1:]
        heading = tables[1].find_all('th')[0].text
        action = 'Deposit' if 'deposit' in heading.lower() else 'Withdrawl'
        multiplier = -1 if action == 'Withdrawl' else 1
        txnDate = emailReceived.strftime("%-m/%-d/%Y")
        txnTime = emailReceived.strftime("%I:%M %p")
        rows.append([txnTime, 'WellsFargo', txnDate, merchant, None,
                     round(float(amount.replace(',', '')) * multiplier, 2), action, None, None, None,
                     None, None])
        return rows

    def process_citi_card_not_present(self, msg_count, rows, body, subject):
        lines = quopri.decodestring(body).decode('utf-8')
        soup = BeautifulSoup(lines, "lxml")
        amount = re.match('(.*) \$((\d{1,3},?)*\d{1,3}\.\d+) transaction', subject).group(2)
        tables = soup.find_all("span", class_="TS-ActionSummaryV2-Value")
        account = 'CITI'
        merchant = tables[0].text
        txnDate = datetime.strptime(tables[2].text, "%m/%d/%Y").strftime("%-m/%-d/%Y")
        txnTime = self.eastern_to_pacific('{} {}'.format(tables[2].text, tables[3].text))
        rows.append([txnTime, account, txnDate, merchant, None,
                     round(float(amount.replace(',', '')) * -1, 2), 'Withdrawl', None, None, None,
                     None, self.get_category(merchant)])
        return rows

    def process_citi_body(self, msg_count, rows, body):
        try:
            lines = quopri.decodestring(body).decode('utf-8')
        except:
            lines = body.decode('utf-8')

        soup = BeautifulSoup(lines, "lxml")
        tables = soup.find_all("span", class_="TS-ActionSummaryV2-Value")
        subject = soup.find_all("span", class_="Headline TS-Headline-Title")[0].text
        if 'merchant credit posted' in subject:
            # credit
            subject_re = re.match('(.*) \$((\d{1,3},?)*\d{1,3}\.\d+) merchant credit posted to your account on (.*)',
                                  subject)
            amount = round(float(subject_re.group(2).replace(',', '')), 2)
            txnDate = datetime.strptime(subject_re.group(4), "%B %d, %Y").strftime("%-m/%-d/%Y")
            txnTime = ''
            merchant = tables[0].text
            account = 'CITI'
            txnType = 'Withdrawl'
        elif 'payment posted to the account' in subject:
            # payment
            # A $1,006.42 payment posted to the account on April 1, 2021
            subject_re = re.match('(.*) \$((\d{1,3},?)*\d{1,3}\.\d+) payment posted to the account on (.*)', subject)
            amount = round(float(subject_re.group(2).replace(',', '')), 2)
            txnDate = datetime.strptime(subject_re.group(4), "%B %d, %Y").strftime("%-m/%-d/%Y")
            txnTime = ''
            merchant = 'DEBIT CITI AUTOPAYPAYMENT'
            account = 'CITI'
            txnType = 'Deposit'
        else:
            # debit
            amount = -1 * round(float(
                re.match('(.*) \$((\d{1,3},?)*\d{1,3}\.\d+) was made on your account', subject).group(2).replace(',',
                                                                                                                 '')),
                                2)
            txnDate = datetime.strptime(tables[2].text, "%m/%d/%Y").strftime("%-m/%-d/%Y")
            txnTime = self.eastern_to_pacific('{} {}'.format(tables[2].text, tables[3].text))
            merchant = tables[1].text
            account = self.dereference_account(tables[0].text)
            txnType = 'Withdrawl'

        category = self.get_category(merchant)
        if category == 'Auto' and amount == -1.0:  # Gas Station Pre Authorizations
            return rows

        rows.append([txnTime, account, txnDate, merchant, None,
                     amount, txnType, None, None, None,
                     None, category])
        return rows

    def process_debits(self, msg_count, rows, tdText, theDate):
        txnDate = theDate.strftime("%-m/%-d/%Y")
        tdText = tdText[
                 tdText.index('For account ending in '):tdText.index('If you authorized this transaction,') - 1].strip()
        # print(tdText)
        txnData = tdText.split('\n')
        account = self.dereference_account(txnData[0].strip()[-5:-1])
        line = re.match('(.*) in the amount of \$((\d{1,3},?)*\d{1,3}\.\d+) by (.*)', txnData[1])
        sameLine = re.match('(.*) by (.*).', txnData[1])
        security = sameLine.group(2)
        rows.append(['', account, txnDate, security, None,
                     round(float(line.group(2).replace(',', '')) * -1, 2), 'Withdrawl', None, None, None,
                     None, None])
        if 'CHASE CREDIT CRD' in security:
            rows.append(['', 'Chase', txnDate, 'Payment', None,
                         round(float(line.group(2).replace(',', '')), 2), 'Payment', None, None, None,
                         None, None])

    # For account ending in 2416:
    # A transfer from the above referenced account to the Fidelity account ending in 0591 in the amount of $100,000.00 has
    # been entered online. Account transfers are typically completed within one business day. No further action is required on your part.
    def process_transfer(self, msg_count, rows, tdText, theDate):
        txnDate = theDate.strftime("%-m/%-d/%Y")
        # tdText = tdText[tdText.index('For account ending in '):tdText.index('If you authorized this transaction,')-1].strip()
        # print(tdText)
        txnData = tdText.split('\n')
        account = self.dereference_account(txnData[0].strip()[-5:-1])

        # line1 = re.match('For account ending in (\d{4}):', txnData[0])
        line2 = re.match('(.*) to the Fidelity account ending in (\d{4}) in the amount of \$((\d{1,3},?)*\d{1,3}\.\d+)',
                         txnData[1])

        toAccount = self.dereference_account(line2.group(2))

        rows.append(['', account, txnDate, 'Transfer to {}'.format(toAccount), None,
                     round(float(line2.group(3).replace(',', '')) * -1, 2), 'Transfer', None, None, None,
                     None, None])
        msg_count = msg_count + 1
        rows.append(['', toAccount, txnDate, 'Transfer from {}'.format(account), None,
                     round(float(line2.group(3).replace(',', '')), 2), 'Transfer', None, None, None,
                     None, None])

    def process_orders(self, msg_count, rows, tdText, theDate):
        if 'A deposit to your account was received' in tdText:
            self.process_deposit(msg_count, rows, tdText, theDate)
            return
        txnDate = theDate.strftime("%-m/%-d/%Y")
        txnData = tdText.strip().split('\n')

        account = self.dereference_account(txnData[0].strip()[-4:])
        action, security, status, totalShares = self.get_order_details(txnData)

        multiplier = -1 if 'Sell' in action else 1
        partialShares = self.get_partial_shares(txnData)
        price = self.get_share_price(txnData)
        if security.startswith('-') and 'PARTIALLY FILLED' in status:
            partialShares = partialShares * 100
        elif security.startswith('-'):
            partialShares = totalShares * 100

        order_num = self.get_order_num(txnData)
        txnTime = self.get_exec_time(txnData)

        rows.append([txnTime, account, txnDate, security, str(multiplier * partialShares),
                     round(price * partialShares * -1 * multiplier, 2), action, status, str(totalShares), price,
                     order_num, None])

    def process_deposit(self, msg_count, rows, tdText, theDate):
        txnData = tdText.strip().split('\n')

        dateStr = re.match('A deposit to your account was received on (.*).', txnData[2])
        txnDateObj = datetime.strptime(dateStr.group(1), "%m/%d/%Y")
        txnDate = txnDateObj.strftime("%-m/%-d/%Y")

        account = self.dereference_account(txnData[0].strip()[-4:])

        txnTime = self.get_exec_time(txnData)

        rows.append([txnTime, account, txnDate, 'Pending', None,
                     0.0, 'Deposit', 'Pending', None, 0.0,
                     None, None])

    def get_order_details(self, lines):
        for line in lines:
            try:
                line2 = re.match('Your order to (.*): (\d+\.\d+) (.*) of (.*) was (.*)', line)
                action = line2.group(1).capitalize()
                security = line2.group(4).replace('<b>', '').replace('</b>', '')
                status = line2.group(5)
                totalShares = float(line2.group(2))
                return action, security, status, totalShares
            except:
                pass

        for line in lines:
            try:
                line2 = re.match('Your order to (.*): \$(.*) of (.*) was (.*)', line)
                action = line2.group(1).capitalize()
                security = line2.group(3).replace('<b>', '').replace('</b>', '')
                status = line2.group(4).replace('<b>', '').replace('.', '')
                return action, security, status, 'TBD'
            except:
                pass

    def get_order_num(self, lines):
        for line in lines:
            try:
                line5 = re.match('Order Number: (.*)', line)
                order_num = line5.group(1)
                return order_num
            except:
                pass

    def get_exec_time(self, lines):
        txnDate = datetime.now().strftime("%-m/%-d/%Y")
        for line in lines:
            try:
                line4 = re.match('(.*)Execution Time: (.*)', line)
                txnTimeStr = line4.group(2).replace('.', '')
                txnTime = self.eastern_to_pacific('{} {}'.format(txnDate, txnTimeStr))
                return txnTime
            except:
                pass

    def get_share_price(self, lines):
        for line in lines:
            try:
                line3 = re.match('(.*): (\d+\.\d+) (.*) @ \$((\d{1,3},?)*\d{1,3}\.\d+)', line)
                price = float(line3.group(4).replace(',', ''))
                return price
            except:
                pass

    def get_partial_shares(self, lines):
        for line in lines:
            try:
                line3 = re.match('(.*): (\d+\.\d+) (.*) @ \$((\d{1,3},?)*\d{1,3}\.\d+)', line)
                partialShares = float(line3.group(2))
                return partialShares
            except:
                pass

    def get_yahoo_option_quote(self, optionTicker):
        # optionTicker = '-QQQ210416P260'
        line1 = re.match('-([A-Z]+)([0-9]{2})([0-9]{2})([0-9]{2})([A-Z]{1})([0-9]{3})', optionTicker)
        ticker = line1.group(1)
        year = line1.group(2)
        month = line1.group(3)
        day = line1.group(4)
        contract = line1.group(5)
        strike = line1.group(6)
        yahooTicker = '{}{}{}{}{}00{}000'.format(ticker, year, month, day, contract, strike)
        url = 'https://finance.yahoo.com/quote/{}?p={}'.format(yahooTicker, yahooTicker)
        print(url)
        options = requests.get(url)
        soup = BeautifulSoup(options.text, "lxml")
        price = soup.find_all("span", class_="Trsdu(0.3s) Fw(b) Fz(36px) Mb(-4px) D(ib)")
        return price[0].text

    def eastern_to_pacific(self, str):
        # str = '03/13/2021 04:10 PM ET'
        eastern = pytz.timezone('US/Eastern')
        pacific = pytz.timezone('US/Pacific')
        date = datetime.strptime(str, "%m/%d/%Y %I:%M %p ET")
        dateest = eastern.localize(date)
        dateeastern = dateest.astimezone(eastern)
        dateeastern
        datepacific = dateest.astimezone(pacific)
        datepacific
        pTimeStr = datepacific.strftime("%I:%M %p")
        return pTimeStr

    # Function to get email content part i.e its body part
    def get_body(self, msg):
        if msg.is_multipart():
            return self.get_body(msg.get_payload(0))
        else:
            return msg.get_payload(None, True)

    # Function to search for a key value pair
    def search(self, key, value, con):
        result, data = con.search(None, key, '"{}"'.format(value))
        return data

    # Function to get the list of emails under this label
    def get_emails(self, result_bytes):
        msgs = []  # all the email data are pushed inside an array
        for num in self, result_bytes[0].split():
            typ, data = con.fetch(num, '(RFC822)')
            msgs.append(data)
        return msgs

    def insert_in_portfolio(self, rowEntry):
        # gc = gspread.authorize(GoogleCredentials.get_application_default())

        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('client_secret.json', scope)
        gc = gspread.authorize(creds)
        # worksheet = gc.open('Portfolio').worksheet('Entry')
        sheet = gc.open_by_url(GOOGLE_PORTFOLIO_WORKSHEET)
        worksheet = sheet.worksheet("Entry")
        endOfWS = worksheet.get_all_values()
        iWS = len(endOfWS) + 1

        for j in range(0, len(rowEntry)):
            print(rowEntry[j])
            cell_list = worksheet.range('A{}:L{}'.format(iWS, iWS))
            for i in range(0, len(rowEntry[j])):
                # print(rowEntry[j][i])
                cell_list[i].value = rowEntry[j][i]
            worksheet.update_cells(cell_list, 'USER_ENTERED')
            iWS = iWS + 1

    def sort_list(self, input):
        for i in input:
            # print(i)
            if i[4] == None:
                i[4] = 0.0
            if i[9] == None:
                i[9] = 0.0
            i[2] = datetime.strptime(i[2], "%m/%d/%Y")

        # print('Before sort: {}'.format(input))

        df = pd.DataFrame(input, columns=['Execution Time', 'Account', 'Date', 'Security', 'Partial Shares', 'Amount',
                                          'Action', 'Status', 'Total Shares', 'Price', 'Order Number', 'Category'])
        df = df.sort_values(by='Date', ascending=True)
        input = df.values.tolist()

        for i in input:
            if i[4] == 0.0:
                i[4] = None
            if i[9] == 0.0:
                i[9] = None
            i[2] = i[2].strftime("%m/%d/%Y")
        # print('After sort: {}'.format(input))

        return input

    def dereference_account(self, num):
        account_suffix = (num or "").strip()
        if not account_suffix:
            return ""

        engine = create_engine(
            f"mysql+pymysql://{MARIADB_USER}:{MARIADB_PASSWORD}@{MARIADB_HOST}:{MARIADB_PORT}/{MARIADB_DATABASE}",
            pool_pre_ping=True,
        )

        with engine.connect() as conn:
            account_type_name = conn.execute(
                text(
                    """
                    SELECT Account_Type_Name
                    FROM Accounts
                    WHERE SUBSTRING_INDEX(Account_Type_Name, '_', -1) = :account_suffix
                    LIMIT 1
                    """
                ),
                {"account_suffix": account_suffix},
            ).scalar()

        if not account_type_name:
            return ""

        name, _, _ = str(account_type_name).rpartition("_")
        return name or ""

    def get_category(self, merchant):
        sub_merchant_list = merchant.split(' ')
        if len(sub_merchant_list) > 1:
            sub_merchant = '{} {}'.format(sub_merchant_list[0], sub_merchant_list[1])
        else:
            sub_merchant = sub_merchant_list[0]
        #merchant_list = self.cat_df.index.values.tolist()
        #choice = process.extractOne(sub_merchant, merchant_list)
        ## print(self.cat_df['category'][choice[0]])
        #return self.cat_df['category'][choice[0]]

    def _get_expenses(self):
        return_from_cache = False
        file_path = CURRENT_MONTH_CREDIT_CSV
        if os.path.exists(file_path):
            mod_time = os.path.getmtime(file_path)
            last_date = datetime.fromtimestamp(mod_time)
            current_date = datetime.now()
            if last_date.date() == current_date.date():
                return_from_cache = True
            else:
                return_from_cache = False
        else:
            return_from_cache = False
        if return_from_cache:
            df = pd.read_csv(file_path, parse_dates=['Date'])
            return df
        else:
            global con, rows
            con = imaplib.IMAP4_SSL(GMAIL_IMAP_SERVER)
            con.login(GMAIL_USER, GMAIL_PASSWORD)
            con.select("Inbox")  # connect to inbox.
            rows = self.process_emails()
            # print('{}: Processing {} email{}...'.format(datetime.now(), len(rows), 's' if len(rows)>1 else ''))
            #if len(rows) > 0:
            #    rows = self.sort_list(rows)
                #self.insert_in_portfolio(rows)
                # df = pd.DataFrame(rows, columns=['Execution Time', 'Account', 'Date', 'Security', 'Partial Shares', 'Amount',
                #                                 'Action', 'Status', 'Total Shares', 'Price', 'Order Number'])
                # df = df.set_index('Index')
                # pd.set_option('display.max_columns', None)
                # pd.set_option('display.max_rows', None)
                # print(df)
                # df.to_csv('email.csv')
                # return df
            con.close()

            if len(rows) == 0:
                df = pd.DataFrame(rows, columns=['Date', 'Description', 'Amount', 'Account','Subscription','Subcategory'])
                return df
            else:
                df = pd.DataFrame(rows, columns=['Date', 'Description', 'Amount', 'Account'])
                categorize = Categorize(df)
                df = categorize.df

            df['Subscription'] = df['Subscription'].fillna('No')
            df['Date'] = pd.to_datetime(df['Date'], format='%m/%d/%Y')
            df.to_csv(CURRENT_MONTH_CREDIT_CSV, index=False)
            return df

    def get_expenses(self, account):
        account_df = self.df[self.df['Account'] == account]
        account_df = self.df.sort_values(by='Date', ascending=False)
        account_df.reset_index(drop=True, inplace=True)
        return account_df

    # schedule.every(10).seconds.do(job)
    # schedule.every(10).minutes.do(job)
    # schedule.every().hour.do(job)
    # schedule.every().day.at("10:30").do(job)
    # schedule.every(5).to(10).minutes.do(job)
    # schedule.every().monday.do(job)
    # schedule.every().wednesday.at("13:15").do(job)
    # schedule.every().minute.at(":17").do(job)

    def main(self, debug):
        # pd.set_option('display.max_columns', None)
        # pd.set_option('display.max_rows', None)
        # print(self.cat_df)
        # print(self.cat_df['category']['Netflix.com Los Gatos CA'])
        # exit(0)

        if debug:
            self.job()
        else:
            schedule.every(5).minutes.do(self.job)
            schedule.every().day.at('16:50').do(self.exit_data).tag('exit')
            # schedule.every(10).seconds.do(self.job)
            # schedule.run_all()

            while True:
                try:
                    schedule.run_pending()
                except:
                    pass
                time.sleep(60)

if __name__ == "__main__":
    g = Gmail()
    #g.main(True)
    #df = g.get_expenses(FIDELITY_VISA)
    print(df)
