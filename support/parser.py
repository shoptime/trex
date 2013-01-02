"""
Various useful parsers
"""
import email
import re
import markdown

# Stolen from mongoengine
EMAIL_REGEX = re.compile(
    r"(^[-!#$%&'*+/=?^_`{}|~0-9A-Z]+(\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*"  # dot-atom
    r'|^"([\001-\010\013\014\016-\037!#-\[\]-\177]|\\[\001-011\013\014\016-\177])*"'  # quoted-string
    r')@(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?$', re.IGNORECASE  # domain
)

def is_email(s):
    """
    Returns true if the string is likely to be a valid email

    @param s: String that may contain an email address
    @type s: str
    @return: Is this an email address?
    @rtype: bool

    >>> is_email('richard@redspider.co.nz')
    True

    >>> is_email('richard@redspider')
    False

    >>> is_email('richard.clark@google.com')
    True

    >>> is_email('richard@foo.redspider')
    False

    >>> is_email('')
    False

    >>> is_email('richard@')
    False

    >>> is_email('@google.com')
    False

    >>> is_email('nigel@mcnie.name')
    True
    """
    return bool(EMAIL_REGEX.match(s))

def set_of_emails(s):
    """
    Retrieve a set of email addresses from a string, separated by linefeed or comma

    @param s: String containing email addresses
    @type s: str
    @return: List of email addresses found
    @rtype: list
    """

    return [b for (a,b) in email.utils.getaddresses([s]) if (b and is_email(b))]

def textarea2html(text):
    """
    Given some text that a user typed into a textarea, format it as HTML.

    This includes attempting to autolink stuff.
    """
    return markdown.markdown(text, output_format='html5', safe_mode='escape', extensions=['urlize'])
