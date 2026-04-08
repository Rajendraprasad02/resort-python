# Reference for WhatsApp Templates

BASIC_DETAILS_TEMPLATE = {
    "name": "basic_details",
    "language": {
        "code": "en"
    },
    "components": [
        {
            "type": "button",
            "sub_type": "flow",
            "index": "0" 
        }
    ]
}

def get_template_payload(recipient_number: str, template_name: str) -> dict:
    """
    Returns the payload required to send a WhatsApp template message.
    """
    if template_name == "basic_details":
        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_number,
            "type": "template",
            "template": {
                "name": "basic_details",
                "language": {"code": "en"},
                "components": [
                    {
                        "type": "button",
                        "sub_type": "flow",
                        "index": "0"
                    }
                ]
            }
        }
    else:
        raise ValueError(f"Template {template_name} not supported.")
