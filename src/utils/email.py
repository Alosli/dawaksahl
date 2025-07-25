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
        
        # Create email message
        from_email_obj = Email(from_email, from_name)
        to_email_obj = To(to_email)
        
        # Create mail object
        mail = Mail(
            from_email=from_email_obj,
            to_emails=to_email_obj,
            subject=subject,
            html_content=html_content
        )
        
        # Add plain text content if provided
        if text_content:
            mail.content = [
                Content("text/plain", text_content),
                Content("text/html", html_content)
            ]
        
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
                        transition: transform 0.2s;
                    }
                    .button:hover {
                        transform: translateY(-2px);
                        box-shadow: 0 6px 8px rgba(37, 99, 235, 0.4);
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
                        
                        <p><strong>لماذا نطلب تأكيد البريد الإلكتروني؟</strong></p>
                        <ul>
                            <li>لضمان أمان حسابك</li>
                            <li>لإرسال تحديثات الطلبات</li>
                            <li>لاستعادة كلمة المرور عند الحاجة</li>
                        </ul>
                        
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
            text_content = f"""
            مرحباً {user_name}!
            
            شكراً لك على التسجيل في دواك سهل. لتأكيد بريدك الإلكتروني، يرجى زيارة الرابط التالي:
            
            {verification_url}
            
            هذا الرابط صالح لمدة 24 ساعة فقط.
            
            مع أطيب التحيات،
            فريق دواك سهل
            """
        else:
            subject = "Email Verification - DawakSahl"
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
                        transition: transform 0.2s;
                    }
                    .button:hover {
                        transform: translateY(-2px);
                        box-shadow: 0 6px 8px rgba(37, 99, 235, 0.4);
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
                        
                        <p><strong>Why do we ask for email verification?</strong></p>
                        <ul>
                            <li>To ensure the security of your account</li>
                            <li>To send you order updates and notifications</li>
                            <li>To help you recover your password if needed</li>
                        </ul>
                        
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
            text_content = f"""
            Welcome {user_name}!
            
            Thank you for registering with DawakSahl. To verify your email address, please visit:
            
            {verification_url}
            
            This link is valid for 24 hours only.
            
            Best regards,
            The DawakSahl Team
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
            html_content = f"""
            <div style="font-family: Arial, sans-serif; direction: rtl;">
                <h2>طلب إعادة تعيين كلمة المرور</h2>
                <p>مرحباً {user_name}،</p>
                <p>لقد طلبت إعادة تعيين كلمة المرور. انقر على الرابط أدناه لإعادة تعيين كلمة المرور:</p>
                <p><a href="{reset_url}" style="background: #2563eb; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">إعادة تعيين كلمة المرور</a></p>
                <p>هذا الرابط ينتهي خلال ساعة واحدة.</p>
                <p>إذا لم تطلب هذا، يرجى تجاهل هذه الرسالة.</p>
            </div>
            """
        else:
            subject = "Password Reset - DawakSahl"
            html_content = f"""
            <div style="font-family: Arial, sans-serif;">
                <h2>Password Reset Request</h2>
                <p>Hello {user_name},</p>
                <p>You requested a password reset. Click the link below to reset your password:</p>
                <p><a href="{reset_url}" style="background: #2563eb; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Reset Password</a></p>
                <p>This link expires in 1 hour.</p>
                <p>If you didn't request this, please ignore this email.</p>
            </div>
            """
        
        return send_email(user_email, subject, html_content)
        
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
        if language == 'ar':
            subject = f"تأكيد الطلب #{order_data.get('order_number')} - دواك سهل"
            html_content = f"""
            <div style="font-family: Arial, sans-serif; direction: rtl;">
                <h2>تأكيد الطلب</h2>
                <p>مرحباً {user_name}،</p>
                <p>تم تأكيد طلبك #{order_data.get('order_number')}.</p>
                <p>المجموع: {order_data.get('total_amount')} ريال يمني</p>
                <p>سنقوم بإشعارك عندما يصبح طلبك جاهزاً.</p>
                <p>شكراً لاختيارك دواك سهل!</p>
            </div>
            """
        else:
            subject = f"Order Confirmation #{order_data.get('order_number')} - DawakSahl"
            html_content = f"""
            <div style="font-family: Arial, sans-serif;">
                <h2>Order Confirmation</h2>
                <p>Hello {user_name},</p>
                <p>Your order #{order_data.get('order_number')} has been confirmed.</p>
                <p>Total: {order_data.get('total_amount')} YER</p>
                <p>We'll notify you when your order is ready.</p>
                <p>Thank you for choosing DawakSahl!</p>
            </div>
            """
        
        return send_email(user_email, subject, html_content)
        
    except Exception as e:
        logger.error(f"Error sending order confirmation email: {str(e)}")
        return {
            'success': False,
            'error': 'Failed to send order confirmation email'
        }
