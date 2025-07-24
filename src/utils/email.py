import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from flask import current_app
import logging

def send_email(to_email, subject, html_content, from_email=None):
    """Send email using SendGrid"""
    try:
        api_key = current_app.config.get('SENDGRID_API_KEY')
        if not api_key:
            current_app.logger.warning("SendGrid API key not configured")
            return False
        
        if not from_email:
            from_email = current_app.config.get('FROM_EMAIL', 'noreply@dawaksahl.com')
        
        message = Mail(
            from_email=from_email,
            to_emails=to_email,
            subject=subject,
            html_content=html_content
        )
        
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        
        current_app.logger.info(f"Email sent successfully to {to_email}, status: {response.status_code}")
        return True
        
    except Exception as e:
        current_app.logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return False

def send_verification_email(email, token, language='ar'):
    """Send email verification email"""
    if language == 'ar':
        subject = "تأكيد البريد الإلكتروني - دواك سهل"
        html_content = f"""
        <div dir="rtl" style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2c5aa0;">مرحباً بك في دواك سهل</h2>
            <p>شكراً لك على التسجيل في منصة دواك سهل. لإكمال عملية التسجيل، يرجى تأكيد بريدك الإلكتروني.</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="http://localhost:3000/verify-email?token={token}" 
                   style="background-color: #2c5aa0; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">
                    تأكيد البريد الإلكتروني
                </a>
            </div>
            <p>إذا لم تقم بإنشاء حساب، يرجى تجاهل هذا البريد الإلكتروني.</p>
            <hr style="margin: 30px 0;">
            <p style="color: #666; font-size: 12px;">
                هذا البريد الإلكتروني تم إرساله من منصة دواك سهل<br>
                لا تقم بالرد على هذا البريد الإلكتروني
            </p>
        </div>
        """
    else:
        subject = "Email Verification - DawakSahl"
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2c5aa0;">Welcome to DawakSahl</h2>
            <p>Thank you for registering with DawakSahl. To complete your registration, please verify your email address.</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="http://localhost:3000/verify-email?token={token}" 
                   style="background-color: #2c5aa0; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">
                    Verify Email
                </a>
            </div>
            <p>If you didn't create an account, please ignore this email.</p>
            <hr style="margin: 30px 0;">
            <p style="color: #666; font-size: 12px;">
                This email was sent from DawakSahl platform<br>
                Please do not reply to this email
            </p>
        </div>
        """
    
    return send_email(email, subject, html_content)

def send_password_reset_email(email, token, language='ar'):
    """Send password reset email"""
    if language == 'ar':
        subject = "إعادة تعيين كلمة المرور - دواك سهل"
        html_content = f"""
        <div dir="rtl" style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2c5aa0;">إعادة تعيين كلمة المرور</h2>
            <p>تلقينا طلباً لإعادة تعيين كلمة المرور لحسابك في دواك سهل.</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="http://localhost:3000/reset-password?token={token}" 
                   style="background-color: #2c5aa0; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">
                    إعادة تعيين كلمة المرور
                </a>
            </div>
            <p>إذا لم تطلب إعادة تعيين كلمة المرور، يرجى تجاهل هذا البريد الإلكتروني.</p>
            <p style="color: #e74c3c; font-size: 14px;">هذا الرابط صالح لمدة 24 ساعة فقط.</p>
            <hr style="margin: 30px 0;">
            <p style="color: #666; font-size: 12px;">
                هذا البريد الإلكتروني تم إرساله من منصة دواك سهل<br>
                لا تقم بالرد على هذا البريد الإلكتروني
            </p>
        </div>
        """
    else:
        subject = "Password Reset - DawakSahl"
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2c5aa0;">Password Reset</h2>
            <p>We received a request to reset your password for your DawakSahl account.</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="http://localhost:3000/reset-password?token={token}" 
                   style="background-color: #2c5aa0; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">
                    Reset Password
                </a>
            </div>
            <p>If you didn't request a password reset, please ignore this email.</p>
            <p style="color: #e74c3c; font-size: 14px;">This link is valid for 24 hours only.</p>
            <hr style="margin: 30px 0;">
            <p style="color: #666; font-size: 12px;">
                This email was sent from DawakSahl platform<br>
                Please do not reply to this email
            </p>
        </div>
        """
    
    return send_email(email, subject, html_content)

def send_order_notification_email(email, order, language='ar'):
    """Send order notification email"""
    if language == 'ar':
        subject = f"تأكيد الطلب #{order.order_number} - دواك سهل"
        html_content = f"""
        <div dir="rtl" style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2c5aa0;">تأكيد الطلب</h2>
            <p>شكراً لك على طلبك من دواك سهل. تم استلام طلبك بنجاح.</p>
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                <h3>تفاصيل الطلب:</h3>
                <p><strong>رقم الطلب:</strong> {order.order_number}</p>
                <p><strong>المجموع:</strong> {order.total_amount} ريال يمني</p>
                <p><strong>حالة الطلب:</strong> {order.order_status.value}</p>
            </div>
            <p>سيتم التواصل معك قريباً لتأكيد التوصيل.</p>
            <hr style="margin: 30px 0;">
            <p style="color: #666; font-size: 12px;">
                هذا البريد الإلكتروني تم إرساله من منصة دواك سهل<br>
                لا تقم بالرد على هذا البريد الإلكتروني
            </p>
        </div>
        """
    else:
        subject = f"Order Confirmation #{order.order_number} - DawakSahl"
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2c5aa0;">Order Confirmation</h2>
            <p>Thank you for your order from DawakSahl. Your order has been received successfully.</p>
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                <h3>Order Details:</h3>
                <p><strong>Order Number:</strong> {order.order_number}</p>
                <p><strong>Total:</strong> {order.total_amount} YER</p>
                <p><strong>Status:</strong> {order.order_status.value}</p>
            </div>
            <p>We will contact you soon to confirm delivery.</p>
            <hr style="margin: 30px 0;">
            <p style="color: #666; font-size: 12px;">
                This email was sent from DawakSahl platform<br>
                Please do not reply to this email
            </p>
        </div>
        """
    
    return send_email(email, subject, html_content)

