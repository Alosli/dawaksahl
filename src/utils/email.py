import os
import logging
from flask import current_app, render_template_string
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, Attachment, FileContent, FileName, FileType, Disposition
import base64

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_email(to_email, subject, html_content, text_content=None, attachments=None):
    """
    Send email using SendGrid API
    
    Args:
        to_email (str): Recipient email address
        subject (str): Email subject
        html_content (str): HTML content of the email
        text_content (str, optional): Plain text content
        attachments (list, optional): List of file paths to attach
    
    Returns:
        dict: Result with success status and message
    """
    try:
        # Get SendGrid configuration from environment
        sendgrid_api_key = os.getenv('SENDGRID_API_KEY')
        from_email = os.getenv('FROM_EMAIL', 'noreply@dawaksahl.com')
        from_name = os.getenv('FROM_NAME', 'DawakSahl')
        
        if not sendgrid_api_key:
            logger.error("SendGrid API key not configured")
            return {
                'success': False,
                'error': 'Email service not configured. Please contact administrator.'
            }
        
        # Create SendGrid client
        sg = SendGridAPIClient(api_key=sendgrid_api_key)
        
        # Create email objects
        from_email_obj = Email(from_email, from_name)
        to_email_obj = To(to_email)
        
        # Create content list
        content_list = []
        
        # Add plain text content if provided
        if text_content:
            content_list.append(Content("text/plain", text_content))
        
        # Add HTML content
        content_list.append(Content("text/html", html_content))
        
        # Create mail object with content
        mail = Mail(
            from_email=from_email_obj,
            to_emails=to_email_obj,
            subject=subject
        )
        
        # Set content properly
        mail.content = content_list
        
        # Add attachments if any
        if attachments:
            for file_path in attachments:
                if os.path.isfile(file_path):
                    with open(file_path, 'rb') as f:
                        file_data = f.read()
                        encoded_file = base64.b64encode(file_data).decode()
                    
                    attached_file = Attachment(
                        FileContent(encoded_file),
                        FileName(os.path.basename(file_path)),
                        FileType('application/octet-stream'),
                        Disposition('attachment')
                    )
                    mail.attachment = attached_file
        
        # Send email
        response = sg.send(mail)
        
        if response.status_code in [200, 201, 202]:
            logger.info(f"Email sent successfully to {to_email} via SendGrid")
            return {
                'success': True,
                'message': 'Email sent successfully',
                'sendgrid_message_id': response.headers.get('X-Message-Id')
            }
        else:
            logger.error(f"SendGrid API error: {response.status_code} - {response.body}")
            return {
                'success': False,
                'error': f'Email service error: {response.status_code}'
            }
        
    except Exception as e:
        logger.error(f"Unexpected error sending email via SendGrid: {str(e)}")
        return {
            'success': False,
            'error': 'Failed to send email. Please try again later.'
        }

def send_verification_email(user_email, user_name, verification_token, language='en'):
    """
    Send email verification email via SendGrid
    
    Args:
        user_email (str): User's email address
        user_name (str): User's full name
        verification_token (str): Email verification token
        language (str): Language preference ('en' or 'ar')
    
    Returns:
        dict: Result with success status and message
    """
    try:
        # Get base URL from environment
        base_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
        verification_url = f"{base_url}/verify-email?token={verification_token}"
        
        if language == 'ar':
            subject = "تأكيد البريد الإلكتروني - دواك سهل"
            
            # Plain text version for Arabic
            text_content = f"""
مرحباً {user_name}!

شكراً لك على التسجيل في دواك سهل. لتأكيد بريدك الإلكتروني، يرجى زيارة الرابط التالي:

{verification_url}

هذا الرابط صالح لمدة 24 ساعة فقط.

مع أطيب التحيات،
فريق دواك سهل
            """
            
            html_template = """
            <!DOCTYPE html>
            <html dir="rtl" lang="ar">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>تأكيد البريد الإلكتروني</title>
                <style>
                    body { 
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                        margin: 0; 
                        padding: 0; 
                        background-color: #f5f5f5; 
                        direction: rtl; 
                    }
                    .container { 
                        max-width: 600px; 
                        margin: 0 auto; 
                        background-color: white; 
                        border-radius: 10px;
                        overflow: hidden;
                        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                    }
                    .header { 
                        background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%); 
                        color: white; 
                        padding: 40px 20px; 
                        text-align: center; 
                    }
                    .logo { 
                        font-size: 32px; 
                        font-weight: bold; 
                        margin-bottom: 10px; 
                        text-shadow: 0 2px 4px rgba(0,0,0,0.3);
                    }
                    .content { 
                        padding: 40px 20px; 
                        line-height: 1.6;
                    }
                    .button { 
                        display: inline-block; 
                        background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%); 
                        color: white; 
                        padding: 15px 30px; 
                        text-decoration: none; 
                        border-radius: 8px; 
                        font-weight: bold; 
                        margin: 20px 0;
                        box-shadow: 0 4px 6px rgba(37, 99, 235, 0.3);
                    }
                    .footer { 
                        background-color: #f8f9fa; 
                        padding: 20px; 
                        text-align: center; 
                        color: #666; 
                        font-size: 14px; 
                        border-top: 1px solid #e9ecef;
                    }
                    .warning { 
                        background-color: #fff3cd; 
                        border: 1px solid #ffeaa7; 
                        padding: 15px; 
                        border-radius: 8px; 
                        margin: 20px 0; 
                        color: #856404; 
                    }
                    .url-box {
                        background-color: #f8f9fa;
                        border: 1px solid #dee2e6;
                        border-radius: 6px;
                        padding: 15px;
                        margin: 15px 0;
                        word-break: break-all;
                        font-family: monospace;
                        color: #2563eb;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <div class="logo">دواك سهل</div>
                        <p style="margin: 0; font-size: 16px; opacity: 0.9;">صيدليتك في تعز</p>
                    </div>
                    <div class="content">
                        <h2 style="color: #2563eb; margin-bottom: 20px;">مرحباً {{ user_name }}!</h2>
                        <p>شكراً لك على التسجيل في دواك سهل، منصة الصيدليات الرائدة في تعز. لإكمال عملية التسجيل وتفعيل حسابك، يرجى تأكيد بريدك الإلكتروني بالنقر على الزر أدناه:</p>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{{ verification_url }}" class="button">تأكيد البريد الإلكتروني</a>
                        </div>
                        
                        <p>إذا لم يعمل الزر أعلاه، يمكنك نسخ ولصق الرابط التالي في متصفحك:</p>
                        <div class="url-box">{{ verification_url }}</div>
                        
                        <div class="warning">
                            <strong>⏰ ملاحظة مهمة:</strong> هذا الرابط صالح لمدة 24 ساعة فقط. إذا لم تقم بتأكيد بريدك الإلكتروني خلال هذه المدة، ستحتاج إلى طلب رابط تأكيد جديد من صفحة تسجيل الدخول.
                        </div>
                        
                        <p>إذا لم تقم بإنشاء حساب في دواك سهل، يرجى تجاهل هذه الرسالة أو التواصل معنا.</p>
                        
                        <p style="margin-top: 30px;">مع أطيب التحيات،<br><strong>فريق دواك سهل</strong></p>
                    </div>
                    <div class="footer">
                        <p><strong>دواك سهل</strong> - أسهل طريقة للحصول على الأدوية في تعز، اليمن</p>
                        <p style="margin: 5px 0;">📧 support@dawaksahl.com | 📱 +967-733-733-870</p>
                        <p style="margin: 0; font-size: 12px; color: #999;">هذه رسالة آلية، يرجى عدم الرد عليها مباشرة.</p>
                    </div>
                </div>
            </body>
            </html>
            """
        else:
            subject = "Email Verification - DawakSahl"
            
            # Plain text version for English
            text_content = f"""
Welcome {user_name}!

Thank you for registering with DawakSahl. To verify your email address, please visit:

{verification_url}

This link is valid for 24 hours only.

Best regards,
The DawakSahl Team
            """
            
            html_template = """
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Email Verification</title>
                <style>
                    body { 
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                        margin: 0; 
                        padding: 0; 
                        background-color: #f5f5f5; 
                    }
                    .container { 
                        max-width: 600px; 
                        margin: 0 auto; 
                        background-color: white; 
                        border-radius: 10px;
                        overflow: hidden;
                        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                    }
                    .header { 
                        background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%); 
                        color: white; 
                        padding: 40px 20px; 
                        text-align: center; 
                    }
                    .logo { 
                        font-size: 32px; 
                        font-weight: bold; 
                        margin-bottom: 10px; 
                        text-shadow: 0 2px 4px rgba(0,0,0,0.3);
                    }
                    .content { 
                        padding: 40px 20px; 
                        line-height: 1.6;
                    }
                    .button { 
                        display: inline-block; 
                        background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%); 
                        color: white; 
                        padding: 15px 30px; 
                        text-decoration: none; 
                        border-radius: 8px; 
                        font-weight: bold; 
                        margin: 20px 0;
                        box-shadow: 0 4px 6px rgba(37, 99, 235, 0.3);
                    }
                    .footer { 
                        background-color: #f8f9fa; 
                        padding: 20px; 
                        text-align: center; 
                        color: #666; 
                        font-size: 14px; 
                        border-top: 1px solid #e9ecef;
                    }
                    .warning { 
                        background-color: #fff3cd; 
                        border: 1px solid #ffeaa7; 
                        padding: 15px; 
                        border-radius: 8px; 
                        margin: 20px 0; 
                        color: #856404; 
                    }
                    .url-box {
                        background-color: #f8f9fa;
                        border: 1px solid #dee2e6;
                        border-radius: 6px;
                        padding: 15px;
                        margin: 15px 0;
                        word-break: break-all;
                        font-family: monospace;
                        color: #2563eb;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <div class="logo">DawakSahl</div>
                        <p style="margin: 0; font-size: 16px; opacity: 0.9;">Your Pharmacy in Taiz</p>
                    </div>
                    <div class="content">
                        <h2 style="color: #2563eb; margin-bottom: 20px;">Welcome {{ user_name }}!</h2>
                        <p>Thank you for registering with DawakSahl, the leading pharmacy platform in Taiz. To complete your registration and activate your account, please verify your email address by clicking the button below:</p>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{{ verification_url }}" class="button">Verify Email Address</a>
                        </div>
                        
                        <p>If the button above doesn't work, you can copy and paste the following link into your browser:</p>
                        <div class="url-box">{{ verification_url }}</div>
                        
                        <div class="warning">
                            <strong>⏰ Important:</strong> This verification link is valid for 24 hours only. If you don't verify your email within this time, you'll need to request a new verification link from the login page.
                        </div>
                        
                        <p>If you didn't create an account with DawakSahl, please ignore this email or contact us.</p>
                        
                        <p style="margin-top: 30px;">Best regards,<br><strong>The DawakSahl Team</strong></p>
                    </div>
                    <div class="footer">
                        <p><strong>DawakSahl</strong> - The easiest way to get medicines in Taiz, Yemen</p>
                        <p style="margin: 5px 0;">📧 support@dawaksahl.com | 📱 +967-733-733-870</p>
                        <p style="margin: 0; font-size: 12px; color: #999;">This is an automated message, please do not reply directly.</p>
                    </div>
                </div>
            </body>
            </html>
            """
        
        # Render template with variables
        html_content = render_template_string(html_template, 
                                            user_name=user_name,
                                            verification_url=verification_url)
        
        return send_email(user_email, subject, html_content, text_content)
        
    except Exception as e:
        logger.error(f"Error sending verification email: {str(e)}")
        return {
            'success': False,
            'error': 'Failed to send verification email'
        }

def send_password_reset_email(user_email, user_name, reset_token, language='en'):
    """
    Send password reset email via SendGrid
    
    Args:
        user_email (str): User's email address
        user_name (str): User's full name
        reset_token (str): Password reset token
        language (str): Language preference ('en' or 'ar')
    
    Returns:
        dict: Result with success status and message
    """
    try:
        base_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
        reset_url = f"{base_url}/reset-password?token={reset_token}"
        
        if language == 'ar':
            subject = "إعادة تعيين كلمة المرور - دواك سهل"
            text_content = f"""
مرحباً {user_name}،

لقد طلبت إعادة تعيين كلمة المرور. لإعادة تعيين كلمة المرور، يرجى زيارة الرابط التالي:

{reset_url}

هذا الرابط ينتهي خلال ساعة واحدة.

إذا لم تطلب هذا، يرجى تجاهل هذه الرسالة.

مع أطيب التحيات،
فريق دواك سهل
            """
            html_content = f"""
            <div style="font-family: Arial, sans-serif; direction: rtl; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                    <h1 style="margin: 0; font-size: 28px;">دواك سهل</h1>
                    <p style="margin: 10px 0 0 0; opacity: 0.9;">صيدليتك في تعز</p>
                </div>
                <div style="background: white; padding: 30px; border-radius: 0 0 10px 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <h2 style="color: #2563eb;">طلب إعادة تعيين كلمة المرور</h2>
                    <p>مرحباً {user_name}،</p>
                    <p>لقد طلبت إعادة تعيين كلمة المرور. انقر على الزر أدناه لإعادة تعيين كلمة المرور:</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{reset_url}" style="background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%); color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">إعادة تعيين كلمة المرور</a>
                    </div>
                    <p style="background: #fff3cd; padding: 15px; border-radius: 8px; color: #856404;"><strong>هام:</strong> هذا الرابط ينتهي خلال ساعة واحدة.</p>
                    <p>إذا لم تطلب هذا، يرجى تجاهل هذه الرسالة.</p>
                </div>
            </div>
            """
        else:
            subject = "Password Reset - DawakSahl"
            text_content = f"""
Hello {user_name},

You requested a password reset. To reset your password, please visit:

{reset_url}

This link expires in 1 hour.

If you didn't request this, please ignore this email.

Best regards,
The DawakSahl Team
            """
            html_content = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                    <h1 style="margin: 0; font-size: 28px;">DawakSahl</h1>
                    <p style="margin: 10px 0 0 0; opacity: 0.9;">Your Pharmacy in Taiz</p>
                </div>
                <div style="background: white; padding: 30px; border-radius: 0 0 10px 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <h2 style="color: #2563eb;">Password Reset Request</h2>
                    <p>Hello {user_name},</p>
                    <p>You requested a password reset. Click the button below to reset your password:</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{reset_url}" style="background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%); color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">Reset Password</a>
                    </div>
                    <p style="background: #fff3cd; padding: 15px; border-radius: 8px; color: #856404;"><strong>Important:</strong> This link expires in 1 hour.</p>
                    <p>If you didn't request this, please ignore this email.</p>
                </div>
            </div>
            """
        
        return send_email(user_email, subject, html_content, text_content)
        
    except Exception as e:
        logger.error(f"Error sending password reset email: {str(e)}")
        return {
            'success': False,
            'error': 'Failed to send password reset email'
        }

def send_order_confirmation_email(user_email, user_name, order_data, language='en'):
    """
    Send order confirmation email via SendGrid
    
    Args:
        user_email (str): User's email address
        user_name (str): User's full name
        order_data (dict): Order information
        language (str): Language preference ('en' or 'ar')
    
    Returns:
        dict: Result with success status and message
    """
    try:
        order_number = order_data.get('order_number', 'N/A')
        total_amount = order_data.get('total_amount', 0)
        
        if language == 'ar':
            subject = f"تأكيد الطلب #{order_number} - دواك سهل"
            text_content = f"""
مرحباً {user_name}،

تم تأكيد طلبك #{order_number}.
المجموع: {total_amount} ريال يمني

سنقوم بإشعارك عندما يصبح طلبك جاهزاً.

شكراً لاختيارك دواك سهل!

مع أطيب التحيات،
فريق دواك سهل
            """
            html_content = f"""
            <div style="font-family: Arial, sans-serif; direction: rtl; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                    <h1 style="margin: 0; font-size: 28px;">دواك سهل</h1>
                    <p style="margin: 10px 0 0 0; opacity: 0.9;">صيدليتك في تعز</p>
                </div>
                <div style="background: white; padding: 30px; border-radius: 0 0 10px 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <h2 style="color: #2563eb;">تأكيد الطلب</h2>
                    <p>مرحباً {user_name}،</p>
                    <p>تم تأكيد طلبك <strong>#{order_number}</strong> بنجاح.</p>
                    <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <p style="margin: 0;"><strong>المجموع: {total_amount} ريال يمني</strong></p>
                    </div>
                    <p>سنقوم بإشعارك عندما يصبح طلبك جاهزاً للاستلام أو التوصيل.</p>
                    <p>شكراً لاختيارك دواك سهل!</p>
                </div>
            </div>
            """
        else:
            subject = f"Order Confirmation #{order_number} - DawakSahl"
            text_content = f"""
Hello {user_name},

Your order #{order_number} has been confirmed.
Total: {total_amount} YER

We'll notify you when your order is ready.

Thank you for choosing DawakSahl!

Best regards,
The DawakSahl Team
            """
            html_content = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                    <h1 style="margin: 0; font-size: 28px;">DawakSahl</h1>
                    <p style="margin: 10px 0 0 0; opacity: 0.9;">Your Pharmacy in Taiz</p>
                </div>
                <div style="background: white; padding: 30px; border-radius: 0 0 10px 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <h2 style="color: #2563eb;">Order Confirmation</h2>
                    <p>Hello {user_name},</p>
                    <p>Your order <strong>#{order_number}</strong> has been confirmed successfully.</p>
                    <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <p style="margin: 0;"><strong>Total: {total_amount} YER</strong></p>
                    </div>
                    <p>We'll notify you when your order is ready for pickup or delivery.</p>
                    <p>Thank you for choosing DawakSahl!</p>
                </div>
            </div>
            """
        
        return send_email(user_email, subject, html_content, text_content)
        
    except Exception as e:
        logger.error(f"Error sending order confirmation email: {str(e)}")
        return {
            'success': False,
            'error': 'Failed to send order confirmation email'
        }



