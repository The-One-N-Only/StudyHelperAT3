def format_apa(title, source_name, url, author=None, year=None):
    if author and year:
        return f"{author}, A. ({year}). {title}. {source_name}. {url}"
    else:
        return f"{source_name}. (n.d.). {title}. Retrieved from {url}"

def format_harvard(title, source_name, url, author=None, year=None):
    if author and year:
        return f"{author} ({year}) '{title}', {source_name}, available at: {url}"
    else:
        return f"{source_name} (n.d.) '{title}', available at: {url}"