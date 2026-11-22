from django.contrib.auth import views as auth
from django.urls import path, reverse_lazy

from . import views

urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", auth.LoginView.as_view(template_name="accounts/login.html", redirect_authenticated_user=True), name="login"),
    path("logout/", auth.LogoutView.as_view(), name="logout"),
    path("onboarding/", views.onboarding, name="onboarding"),
    path("onboarding/skills/", views.onboarding_skills, name="onboarding_skills"),
    path("account/", views.account, name="account"),
    path("password-reset/", auth.PasswordResetView.as_view(template_name="accounts/password_reset.html",
         email_template_name="accounts/password_reset_email.txt", subject_template_name="accounts/password_reset_subject.txt",
         success_url=reverse_lazy("password_reset_done")), name="password_reset"),
    path("password-reset/sent/", auth.PasswordResetDoneView.as_view(template_name="accounts/password_reset_done.html"), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", auth.PasswordResetConfirmView.as_view(template_name="accounts/password_reset_confirm.html",
         success_url=reverse_lazy("password_reset_complete")), name="password_reset_confirm"),
    path("reset/done/", auth.PasswordResetCompleteView.as_view(template_name="accounts/password_reset_complete.html"), name="password_reset_complete"),
]
