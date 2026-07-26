import logging

from flask import render_template


def register_error_handlers(app):
    @app.errorhandler(Exception)
    def handle_exception(e):
        logging.error(f"Unhandled exception: {str(e)}")
        return render_template('error.html'), 500

    @app.errorhandler(404)
    def not_found(_error):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(_error):
        return render_template('500.html'), 500
