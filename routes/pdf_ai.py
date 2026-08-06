from flask import Blueprint, render_template

pdf_ai = Blueprint(
    "pdf_ai",
    __name__
)

@pdf_ai.route("/pdf-chat")
def pdf_chat():

    return render_template(
        "pdf_chat.html"
    )