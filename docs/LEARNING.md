# Learning expansion
Instructors create course discussion topics; enrolled students and assigned instructors reply. Admins can close discussions. Password reset uses Django's expiring token flow and requires a configured SMTP server in production. Development uses an in-memory email backend to avoid logging password reset tokens. SMTP delivery is unverified.
