from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, FloatField, SubmitField, SelectField
from flask_wtf.file import FileField, FileAllowed
from wtforms.validators import DataRequired, Optional, NumberRange


class InventoryForm(FlaskForm):
    make = StringField('Make', validators=[DataRequired()])
    model = StringField('Model', validators=[DataRequired()])
    year = IntegerField('Year', validators=[
                        DataRequired(), NumberRange(min=1900, max=2100)])
    purchase_price = FloatField('Purchase Price', validators=[DataRequired()])
    selling_price = FloatField('Selling Price', validators=[Optional()])
    mileage = FloatField('Mileage (km)', validators=[Optional()])
    photo = FileField('Vehicle Photo', validators=[
                      Optional(), FileAllowed(['jpg', 'jpeg', 'png'], 'Images only!')])
    submit = SubmitField('Add Vehicle')


class ExpenseForm(FlaskForm):
    vehicle_id = SelectField(
        'Select Vehicle', coerce=int, validators=[DataRequired()])
    expense_category = StringField(
        'Expense Category', validators=[DataRequired()])
    expense_amount = FloatField('Expense Amount', validators=[DataRequired()])
    submit = SubmitField('Add Expense')

class EditVehicleForm(FlaskForm):
    vehicle_id = SelectField('Select Vehicle', coerce=int, validators=[DataRequired()])
    make = StringField('Make', validators=[Optional()])
    model = StringField('Model', validators=[Optional()])
    year = IntegerField('Year', validators=[Optional()])
    purchase_price = FloatField('Purchase Price', validators=[Optional()])
    selling_price = FloatField('Selling Price', validators=[Optional()])
    mileage = FloatField('Mileage (km)', validators=[Optional()])
    photo = FileField('Vehicle Photo', validators=[Optional(), FileAllowed(['jpg', 'jpeg', 'png'], 'Images only!')])
    submit = SubmitField('Update Vehicle')

