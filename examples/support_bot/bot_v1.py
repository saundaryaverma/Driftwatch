"""Demo support bot for a made-up outdoor gear store, version 1.
Rule-based so the demo runs instantly with no API key. Swap in any real model
with --target openai:<model> or an http target."""
import json
import re


def reply(messages):
    text = messages[-1]["content"].lower()

    if re.search(r"ignore (all|your|previous)", text) or "discount code" in text:
        return "I can't change pricing or create discount codes, but I can help with orders and returns."
    if "email" in text or "phone" in text or "address" in text:
        return "I can't share other customers' information. I can only help with your own account."
    if "json" in text:
        order = re.search(r"\d{4}", text)
        return json.dumps({"order_id": order.group(0) if order else None, "status": "shipped"})
    if "return" in text or "refund" in text:
        return "You can return unused items within 30 days of delivery for a full refund."
    if "ship" in text:
        return "Standard shipping takes 3-5 business days."
    if "where is my order" in text or "order status" in text:
        return "Happy to check. What's your order number?"
    if "sale" in text:
        return "I don't know yet. We haven't announced dates for the next sale."
    if re.search(r"\b(hi|hello|hey)\b", text):
        return "Hi! I can help with orders, shipping, and returns. What do you need?"
    return "I'm not sure about that. I can help with orders, shipping, and returns."
