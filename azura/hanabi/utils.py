import typing


def is_optional(field):
    return typing.get_origin(field) is typing.Union and \
           type(None) in typing.get_args(field)


def cc_to_sc(string) -> str:
    """
    Convert camelCase to snake_case.

    "Why bother?"
    Because I'm autistic and hate inconsistency,
    but also refuse to change my own ways...mainly
    due to the autism.
    """
    out = ""
    upper = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    for char in string:
        if char in upper:
            out += "_" + char.lower()
        else:
            out += char
    return out


def cc_to_sc_dict(d: dict) -> dict:
    out = {}

    for key, value in d.items():
        if isinstance(value, dict):
            out[cc_to_sc(key)] = cc_to_sc_dict(value)
        else:
            out[cc_to_sc(key)] = value
    return out


def generate_loading_bar(
        ratio, 
        complete_bar="=", 
        incomplete_bar="-", 
        arrow=">", 
        l_end="[", 
        r_end="]", 
        length=30
    ):
    complete_bars = int(round(length * ratio, 0))
    incomplete_bars = length - complete_bars
    if ratio >= 1:
        arrow = complete_bar
    return f"{l_end}{complete_bar * complete_bars}{arrow}{incomplete_bar * incomplete_bars}{r_end}"


def generate_volume_bar(volume):
    ratio = 1.0  if volume >= 100 else volume / 100
    return generate_loading_bar(
        ratio,
        arrow="|"
    )


def timestamp_from_ms(ms):
    s = ms // 1000
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    if s < 10:
        s = f"0{s}"

    if h != 0:
        if m < 10:
            m = f"0{m}"
        return f"{h}:{m}:{s}"
    else:
        return f"{m}:{s}"