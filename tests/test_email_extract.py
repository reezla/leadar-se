from lead_finder.providers.email_extract import suggested_email

ADESSO = """
<html><body>
  <h3>Adesso Bygg AB</h3>
  <p>Von post väg 7, 444 48 Stenungsund</p>
  <h4><span>Roger</span> <span>Andersen</span></h4>
  <h5>Tele: 0706-712271 eller 0303-69744</h5>
  <h5>E.post: förnamn@adessobygg.se</h5>
  <h4>Nic Larson</h4>
  <h5>E.post: förnamn@adessobygg.se</h5>
</body></html>
"""


def test_fornamn_template_uses_the_first_person_above_it() -> None:
    address = suggested_email(ADESSO, page_url="https://www.adessobygg.se/kontakta-oss-2/")
    assert address == "roger@adessobygg.se"


def test_fornamn_efternamn_template_uses_both_names() -> None:
    html = """
    <html><body>
      <h4>Roger Andersen</h4>
      <p>förnamn.efternamn@adessobygg.se</p>
    </body></html>
    """
    address = suggested_email(html, page_url="https://adessobygg.se/")
    assert address == "roger.andersen@adessobygg.se"


def test_obfuscated_at_is_still_a_template() -> None:
    html = "<html><body><p>Nic Larson</p><p>E-post: förnamn(at)adessobygg.se</p></body></html>"
    assert suggested_email(html, page_url="https://adessobygg.se/") == "nic@adessobygg.se"


def test_generic_inbox_beats_a_fornamn_template() -> None:
    html = ADESSO.replace(
        "<h3>Adesso Bygg AB</h3>",
        '<h3>Adesso Bygg AB</h3><a href="mailto:info@adessobygg.se">info</a>',
    )
    assert suggested_email(html, page_url="https://adessobygg.se/") == "info@adessobygg.se"


def test_fornamn_without_a_person_is_not_an_address() -> None:
    html = "<html><body><p>E.post: förnamn@adessobygg.se</p></body></html>"
    assert suggested_email(html, page_url="https://adessobygg.se/") is None


def test_published_personal_email_is_kept_when_no_generic_inbox() -> None:
    html = """
    <html><body>
      <p>Anna Svensson anna@gmail.com</p>
      <p>Erik Holm erik@adessobygg.se</p>
    </body></html>
    """
    assert suggested_email(html, page_url="https://adessobygg.se/") == "erik@adessobygg.se"


def test_company_name_is_not_used_as_the_first_name() -> None:
    html = "<html><body><h3>Adesso Bygg</h3><p>förnamn@adessobygg.se</p></body></html>"
    assert suggested_email(html, page_url="https://adessobygg.se/") is None
