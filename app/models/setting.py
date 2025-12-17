# app/models/setting.py

class Setting:
    """Base Setting class"""
    
    @classmethod
    def get_value(cls, key, default=None):
        # This will be implemented after db is available
        pass
    
    @classmethod
    def set_value(cls, key, value):
        # This will be implemented after db is available
        pass

def get_setting_model(db):
    class SettingModel(Setting, db.Model):
        __tablename__ = 'settings'
        
        id = db.Column(db.Integer, primary_key=True)
        key = db.Column(db.String(100), unique=True, nullable=False)
        value = db.Column(db.Text, nullable=True)
        updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), 
                              onupdate=db.func.current_timestamp())
        
        @classmethod
        def get_value(cls, key, default=None):
            setting = cls.query.filter_by(key=key).first()
            return setting.value if setting else default
        
        @classmethod
        def set_value(cls, key, value):
            setting = cls.query.filter_by(key=key).first()
            if setting:
                setting.value = value
            else:
                setting = cls(key=key, value=value)
                db.session.add(setting)
            db.session.commit()
            return setting
        
        def __repr__(self):
            return f'<Setting {self.key}>'
    
    return SettingModel