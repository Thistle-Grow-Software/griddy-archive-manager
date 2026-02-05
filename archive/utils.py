def numberify(data: dict):
    for key, value in data.items():
        try:
            value = int(value)
        except ValueError:
            try:
                value = float(value)
            except ValueError:
                value = value
        data[key] = value
    return data
