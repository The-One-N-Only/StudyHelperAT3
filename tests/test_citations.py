import src.citations as citations

def test_format_apa_with_author_year():
    result = citations.format_apa("Title", "Source", "url.com", "Author", "2023")
    assert result == "Author, A. (2023). Title. Source. url.com"

def test_format_apa_without_author():
    result = citations.format_apa("Title", "Source", "url.com")
    assert result == "Source. (n.d.). Title. Retrieved from url.com"

def test_format_harvard_with_author_year():
    result = citations.format_harvard("Title", "Source", "url.com", "Author", "2023")
    assert result == "Author (2023) 'Title', Source, available at: url.com"

def test_format_harvard_without_author():
    result = citations.format_harvard("Title", "Source", "url.com")
    assert result == "Source (n.d.) 'Title', available at: url.com"