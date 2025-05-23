


def update_dict(d1: dict, d2: dict) -> dict:
    """d2의 값이 None, [], '' 등이 아닌 경우에만 d1을 업데이트"""
    result = d1.copy()
    for k, v in d2.items():
        if isinstance(v, dict) and k in result and isinstance(result[k], dict):
            result[k] = update_dict(result[k], v)
        elif v:
            result[k] = v
    return result