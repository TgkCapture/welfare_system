# app/controllers/welfare_controller.py
from flask import render_template, current_app

class WelfareController:
    """Handles welfare rules business logic"""
    
    @staticmethod
    def welfare_rules():
        """Public endpoint for welfare rules - no login required"""
        return render_template('main/welfare_rules.html', 
                             version=current_app.version)