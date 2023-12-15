import secrets


def generate_order_id():
	return secrets.token_urlsafe(45)
