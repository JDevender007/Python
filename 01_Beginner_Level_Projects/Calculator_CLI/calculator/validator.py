def is_number(v):
    try:
        float(v); 
        return True
    except ValueError:
        return False
