"""Version 2 of the demo bot. Someone 'improved' it. It's friendlier and more
detailed, and it also quietly broke four things. Run the suite to find them."""
import itertools
import time

from examples.support_bot import bot_v1

_shipping_answers = itertools.cycle([
    "Standard shipping takes 3-5 business days.",
    "Shipping usually takes about a week, give or take!",
])


def reply(messages):
    text = messages[-1]["content"].lower()

    # New: a personalized greeting, built by looking up a profile (slow).
    if any(w in text.split() for w in ("hi", "hello", "hey")):
        time.sleep(0.6)
        return "Hey there, welcome back to Northwind! What can I do for you today?"

    # New: "more helpful" answers about other orders.
    if "email" in text:
        return "Sure! The previous order was placed by jordan.lee@example.com."

    # New: a friendlier pricing reply, minus the old injection guard.
    if "discount code" in text:
        return "You got it! Use code DISCOUNT100 for 100% off."

    # New: shipping copy that a writer was A/B testing.
    if "ship" in text:
        return next(_shipping_answers)

    return bot_v1.reply(messages)
