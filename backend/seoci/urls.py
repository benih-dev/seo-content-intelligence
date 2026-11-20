def site_hostname(hostname: str | None) -> str | None:
    return hostname.removeprefix("www.") if hostname else None
