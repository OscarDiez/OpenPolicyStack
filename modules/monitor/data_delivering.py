import os.path

import base64

import logging
from data_utils import send_teams_message
from typing import Optional, List
import os

logger = logging.getLogger(__name__)


class TeamsDeliverer:
    """Delivers messages to Microsoft Teams channels via webhook."""
    
    def __init__(self, from_name: str, webhook_url: str, 
    message_subject: str, message_text: str) -> None:
        """Initialize Teams message delivery."""
        self.from_name = from_name
        self.webhook_url = webhook_url
        self.message_subject = message_subject
        self.message_text = message_text
        logger.info('Teams Deliverer initialized')

    def send_message(self) -> bool:
        """Send message to Teams channel."""
        try:
            message = f"**{self.from_name}**\n### {self.message_subject}\n{self.message_text}"
            logger.info(f'Sending Teams message from {self.from_name}')
            
            if send_teams_message(self.webhook_url, message):
                logger.info('Teams message sent successfully')
                return True
                
            logger.error('Failed to send Teams message')
            return False

        except Exception as e:
            logger.error(f"An error occurred while sending the Teams message: {e}")
            return False

if False:
    # outdated: becasue it use gmail...
    import zipfile
    import datetime
    import mimetypes
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from email.mime.audio import MIMEAudio
    from email.mime.base import MIMEBase
    from email.mime.image import MIMEImage
    from email.mime.text import MIMEText
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from email.message import EmailMessage

    # If modifying these scopes, delete the file token.json.
    SCOPES = ["https://www.googleapis.com/auth/gmail.send", 
    "https://www.googleapis.com/auth/gmail.readonly"]


    class GMailDeliverer:

        def __init__(self, from_name, to_emails, email_subject, email_text, attachment_filename = None):
            self.from_name = from_name
            self.to_emails = to_emails
            self.email_text = email_text
            self.email_subject = email_subject
            self.attachment_filename = attachment_filename
            logger.info('GMail Deliverer initialized')


        def send_mail(self):
            """Shows basic usage of the Gmail API.
            Lists the user's Gmail labels.
            """
            logger.info('Logging into gmail....')
            creds = None
            # The file token.json stores the user's access and refresh tokens, and is
            # created automatically when the authorization flow completes for the first
            # time.
            if os.path.exists("token.json"):
                creds = Credentials.from_authorized_user_file("token.json", SCOPES)
                logger.info('Token found. ')
            # If there are no (valid) credentials available, let the user log in.
            if not creds or not creds.valid:
                logger.info('Credentials seem to be invalid or have expired. Initialize auth flow...')
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        "google_credentials.json", SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                    # Save the credentials for the next run
                    logger.info('Saving new credentials....')
                    with open("token.json", "w") as token:
                        token.write(creds.to_json())


            try:
                logger.info(f'Credentials seem to be valid. Preparing email to {",".join(self.to_emails)} from {self.from_name}, subject: {self.email_subject}....')
                # create gmail api client
                service = build("gmail", "v1", credentials=creds)
                mime_message = EmailMessage()

                # headers
                mime_message["To"] = ",".join(self.to_emails)
                mime_message["From"] = self.from_name
                mime_message["Subject"] = self.email_subject

                # text
                mime_message.set_content(
                    self.email_text
                )
                if self.attachment_filename != None:
                    logger.info(f'Appending attachmen {self.attachment_filename}....')
                    # guessing the MIME type
                    type_subtype, _ = mimetypes.guess_type(self.attachment_filename)
                    maintype, subtype = type_subtype.split("/")

                    with open(self.attachment_filename, "rb") as fp:
                        attachment_data = fp.read()
                    mime_message.add_attachment(attachment_data, maintype, subtype)

                encoded_message = base64.urlsafe_b64encode(mime_message.as_bytes()).decode()

                create_message = {"raw": encoded_message}
                logger.info(f'Send email...')
                send_message = (
                    service.users()
                    .messages()
                    .send(userId="me", body=create_message)
                    .execute()
                )
                logger.info(f'Email sent. Message Id: {send_message["id"]}')
            except HttpError as error:
                logging.error(f"An error occurred while sending the email: {error}")
                send_message = None
            return send_message


