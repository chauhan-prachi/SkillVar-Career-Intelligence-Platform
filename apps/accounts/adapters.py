from allauth.account.adapter import DefaultAccountAdapter


class ClosedLocalSignupAdapter(DefaultAccountAdapter):
    """allauth's own sign-up page stays closed: local registration happens on SkillVar's /accounts/register/."""

    def is_open_for_signup(self, request):
        return False
