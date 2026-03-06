"""Email service for sending content via SendGrid"""
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from flask import current_app


class EmailService:
    """Send content via SendGrid email"""

    def __init__(self):
        api_key = current_app.config.get('SENDGRID_API_KEY') or os.environ.get('SENDGRID_API_KEY')
        self.api_key = api_key.strip() if api_key else None
        self.from_email = current_app.config.get('SENDGRID_FROM_EMAIL', 'noreply@aeoplatform.local')
        self.client = None
        if self.api_key:
            self.client = SendGridAPIClient(self.api_key)
            print(f"EmailService initialized with API key: {self.api_key[:10]}...")
            print(f"From email: {self.from_email}")

    def send_content_for_review(self, to_email, content, share_url, sender_name, message=None):
        """Send a teaser email with a link to view shared content

        Args:
            to_email: Recipient email address
            content: GeneratedContent object
            share_url: URL to view the full content
            sender_name: Name of the person sharing
            message: Optional personal message

        Returns:
            tuple: (success: bool, error_message: str or None)
        """
        if not self.client:
            return False, "SendGrid API key not configured"

        try:
            subject = f"{sender_name} shared \"{content.title}\" with you"

            # Build a short content snippet (first 200 chars, no markdown)
            import re
            snippet = re.sub(r'[#*_\[\]()]', '', content.content[:200]).strip()
            if len(content.content) > 200:
                snippet += "..."

            message_block_html = ""
            message_block_text = ""
            if message:
                from markupsafe import escape
                message_block_html = f"""
                <div style="margin: 20px 0; padding: 15px; background-color: #f9fafb; border-left: 4px solid #4F46E5; border-radius: 4px;">
                    <p style="margin: 0; color: #374151; font-style: italic;">&ldquo;{escape(message)}&rdquo;</p>
                </div>"""
                message_block_text = f'\n"{message}"\n'

            html_content = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <p style="color: #374151;"><strong>{sender_name}</strong> shared content with you for review:</p>

                <div style="margin: 20px 0; padding: 20px; background-color: #f3f4f6; border-radius: 8px;">
                    <h2 style="margin: 0 0 8px 0; color: #111827; font-size: 20px;">{content.title}</h2>
                    <p style="margin: 0 0 12px 0; color: #6b7280; font-size: 14px;">
                        {content.word_count} words &middot; SEO Keyphrase: {content.seo_keyphrase or 'N/A'}
                    </p>
                    <p style="margin: 0; color: #4b5563; font-size: 14px;">{snippet}</p>
                </div>
                {message_block_html}
                <div style="margin: 30px 0; text-align: center;">
                    <a href="{share_url}" style="display: inline-block; padding: 14px 32px; background-color: #4F46E5; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: bold;">View Full Content</a>
                </div>

                <p style="color: #9ca3af; font-size: 12px; text-align: center;">
                    This link expires in 30 days.<br>
                    Sent from AEO Platform
                </p>
            </div>
            """

            plain_text = f"""{sender_name} shared content with you for review:

"{content.title}"
{content.word_count} words | SEO Keyphrase: {content.seo_keyphrase or 'N/A'}

{snippet}
{message_block_text}
View the full content and download options here:
{share_url}

This link expires in 30 days.
Sent from AEO Platform
"""

            mail = Mail(
                from_email=self.from_email,
                to_emails=to_email,
                subject=subject,
                plain_text_content=plain_text,
                html_content=html_content
            )

            response = self.client.send(mail)

            print(f"SendGrid response status: {response.status_code}")

            if response.status_code in [200, 201, 202]:
                return True, None
            else:
                return False, f"SendGrid returned status {response.status_code}: {response.body}"

        except Exception as e:
            import traceback
            print(f"SendGrid error: {e}")
            print(traceback.format_exc())
            return False, self._extract_error(e)

    def send_invitation_email(self, to_email, inviter, invite_url):
        """Send team invitation email

        Args:
            to_email: Recipient email address
            inviter: User object who sent the invitation
            invite_url: Full URL to accept the invitation

        Returns:
            tuple: (success: bool, error_message: str or None)
        """
        if not self.client:
            return False, "SendGrid API key not configured"

        try:
            subject = f"You've been invited to join {inviter.tenant.name} on AEO Platform"

            html_content = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #4F46E5;">You're Invited!</h2>
                <p><strong>{inviter.first_name} {inviter.last_name}</strong> has invited you to join
                <strong>{inviter.tenant.name}</strong> on AEO Platform.</p>

                <p>AEO Platform helps brands optimize their visibility in AI-powered search engines.</p>

                <div style="margin: 30px 0; text-align: center;">
                    <a href="{invite_url}" style="display: inline-block; padding: 14px 32px; background-color: #4F46E5; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: bold;">Accept Invitation</a>
                </div>

                <p style="color: #666; font-size: 13px;">Or copy and paste this link into your browser:<br>
                <a href="{invite_url}" style="color: #4F46E5;">{invite_url}</a></p>

                <p style="color: #666; font-size: 14px; margin-top: 30px;">
                    This invitation will expire in 7 days.<br>
                    If you didn't expect this invitation, you can ignore this email.
                </p>
            </div>
            """

            # Create plain text version
            plain_text = f"""You've been invited to join {inviter.tenant.name} on AEO Platform.

{inviter.first_name} {inviter.last_name} has invited you to join their team.

To accept this invitation, visit the following link:
{invite_url}

This invitation will expire in 7 days.

If you didn't expect this invitation, you can ignore this email.
"""

            from sendgrid.helpers.mail import Content

            mail = Mail(
                from_email=self.from_email,
                to_emails=to_email,
                subject=subject,
                plain_text_content=plain_text,
                html_content=html_content
            )

            response = self.client.send(mail)

            if response.status_code in [200, 201, 202]:
                return True, None
            else:
                return False, f"SendGrid returned status {response.status_code}"

        except Exception as e:
            import traceback
            print(f"SendGrid invitation error: {e}")
            print(traceback.format_exc())
            error_msg = self._extract_error(e)
            return False, error_msg

    @staticmethod
    def _extract_error(e):
        """Extract detailed error message from SendGrid API exceptions."""
        status = getattr(e, 'status_code', None)
        body = getattr(e, 'body', None)
        if status and body:
            try:
                body_str = body.decode('utf-8') if isinstance(body, bytes) else str(body)
            except Exception:
                body_str = str(body)
            return f"HTTP {status}: {body_str}"
        return str(e)
