from email.message import EmailMessage
import logging
import os
import smtplib

import requests

from logging_config import get_logger

logging = get_logger(__name__)

def send_email(subject:str, report:str):
  logging.debug(f"\n--- Calling send_email ---")
  logging.debug(f"Email Subject: {subject}")
  logging.debug(f"Email Report (first 200 chars): {report[:200]}...")

  """ Sends an email with a subject and the consolidated report """
  # Set environment variables for credentials
  SMTP_HOST = os.environ.get("RESEND_SERVER") 
  SMTP_PORT = 465 # Use port 465 for implicit SSL
  SMTP_USERNAME = os.environ.get("RESEND_USER") 
  SMTP_PASSWORD = os.environ.get("RESEND_API_KEY") 

  msg = EmailMessage()
  msg.set_content("This is the plain text body of the email sent via smtplib and Resend.")
  msg.add_alternative(f"""
  {report}
  """, subtype='html')

  msg['Subject'] = subject
  msg['From'] = os.environ.get("FROM_EMAIL") 
  msg['To'] = os.environ.get("TO_EMAIL") 

  try:
      # Connect to the SMTP server using SSL
      with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
          server.login(SMTP_USERNAME, SMTP_PASSWORD)
          server.send_message(msg)
      logging.debug("Email sent successfully!")
  except Exception as e:
      logging.error(f"Error: {e}")

def send_sms_text(text_message:str):
    logging.debug(f"\n--- Calling send_sms_text ---")
    logging.debug(f"SMS Message: {text_message}")

    """ Sends an text message using SMS """
    pushover_user = os.getenv("PUSHOVER_USER")
    pushover_token = os.getenv("PUSHOVER_TOKEN")
    pushover_url = os.getenv("PUSHOVER_URL")

    logging.debug(f"Push: {text_message}")
    payload = {"user": pushover_user, "token": pushover_token, "message": text_message}
    requests.post(pushover_url, data=payload)

