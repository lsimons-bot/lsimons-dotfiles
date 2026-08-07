# AWS CLI configuration
# Uses default ~/.aws/config for region and output settings
#
# saml2aws (SSO login via Okta) uses ~/.saml2aws, configured by install.py
# with the Browser provider, since our Okta org runs OIE and the default
# Okta provider always fails with 401 against it. Run `saml2aws login
# --force` to authenticate; a browser window opens for FastPass/Okta Verify.
