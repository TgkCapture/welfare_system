from flask import Flask, render_template
from utils.auth import login_manager
from utils.gsheets import init_gsheets
from utils.models import db
from config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    init_gsheets(app)
    
    # Register blueprints/routes
    from utils import auth, reports
    app.register_blueprint(auth.bp)
    app.register_blueprint(reports.bp)
    
    @app.route('/')
    def index():
        return render_template('index.html')
    
    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)