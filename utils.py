def time_string(s):
    if s < 60:
        return s

    m = 0
    h = 0

    while s >= 60:
        m += 1
        s -= 60

    while m >= 60:
        h += 1
        m -= 60

    return f"{(str(h)+'h ')*(1 if h else 0)}{(str(m)+'m ')*(1 if m else 0)}{(str(s)+'s')*(1 if s else 0)}"
