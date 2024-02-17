def truncate(string: str, limit: int, truncateby: int = 3, char: str = ".") -> str:
    if len(string) >= limit:
        return string[:limit-truncateby] + (char * truncateby)
    return string