import datetime
from email.message import EmailMessage
import logging
import os
import smtplib
from zoneinfo import ZoneInfo

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken
import requests

from ai_client_model_registry import ModelClientRegistry
from logging_config import get_logger
from prompts import report_agent_system_prompt

logging = get_logger(__name__)

def get_current_date() -> str:
    central = ZoneInfo("America/Chicago")  # Handles CST/CDT automatically
    return datetime.now(central).strftime("%Y-%m-%d")

def send_email(subject:str, report:str):
  logging.debug("\n--- Calling send_email ---")
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
    logging.debug("\n--- Calling send_sms_text ---")
    logging.debug(f"SMS Message: {text_message}")

    """ Sends an text message using SMS """
    pushover_user = os.getenv("PUSHOVER_USER")
    pushover_token = os.getenv("PUSHOVER_TOKEN")
    pushover_url = os.getenv("PUSHOVER_URL")

    logging.debug(f"Push: {text_message}")
    payload = {"user": pushover_user, "token": pushover_token, "message": text_message}
    requests.post(pushover_url, data=payload)

async def send_report(all_signals_for_report):

    report_agent = AssistantAgent(
        name="Report_Agent",
        model_client=ModelClientRegistry.get_or_email_model_client(),
        tools=[send_email, send_sms_text],
        reflect_on_tool_use=True,
        max_tool_iterations=3,
        system_message=report_agent_system_prompt
    )

    logging.debug("Sending email and text notification")
    message = TextMessage(
        content=f"""Please send an email with these stock and option recommendations : {all_signals_for_report}
        Send an sms alert once the email has been sent
        """, 
        source="user"
    )

    await report_agent.on_messages(messages=[message], cancellation_token=CancellationToken())


