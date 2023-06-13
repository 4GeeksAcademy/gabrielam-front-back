"""
This module takes care of starting the API Server, Loading the DB and Adding the endpoints
"""
from datetime import timedelta
from flask import Flask, request, jsonify, url_for, Blueprint
from api.models import db, User, TokenBlockedList, Restaurant, Pedidos, Platos,Restaurantplatos, Suscriptions
from api.utils import generate_sitemap, APIException
from flask_bcrypt import Bcrypt
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity, get_jwt, get_jti
import os
import openai

openai.api_key = os.getenv("OPENAI_API_KEY")
api = Blueprint('api', __name__)
app = Flask(__name__)
bcrypt = Bcrypt(app)

@api.route('/login', methods=['POST'])
def user_login():
    user_email= request.json.get('email')
    user_password= request.json.get('password')

    # buscar usuario por correo
    user=User.query.filter_by(email=user_email).first()
    if (user is None):
        return jsonify({"message": "user not found"}),401
    
    #Verificar la clave
    if not bcrypt.check_password_hash(user.password, user_password):
        return jsonify({"message": "Wrong Password"}),401
    
    #Generar el token
    access_token= create_access_token(identity=user.id)
    access_jti=get_jti(access_token)
    refresh_token=create_refresh_token(identity=user.id, additional_claims= {"accessToken": access_jti})

    #Retornar el token
    return jsonify({"accessToken": access_token, "refreshToken": refresh_token})

#Refrescar el token
@api.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def user_refresh():
    #Identificadores de tokens viejos

    jti_refresh=get_jwt()["jti"]
    jti_access=get_jwt()["accessToken"]

    #Bloquear los tokens viejos
    accessRevoked= TokenBlockedList(jti=jti_access)
    refreshRevoked= TokenBlockedList(jti=jti_refresh)
    db.session.add(accessRevoked)
    db.session.add(refreshRevoked)
    db.session.commit()

    #Generar nuevos tokens
    user_id=get_jwt_identity()
    access_token= create_access_token(identity=user_id)
    refresh_token=create_refresh_token(identity=user_id, additional_claims= {"accessToken": access_jti})

    #Retornar el token
    return jsonify({"accessToken": access_token})

@api.route('/logout', methods=['POST'])
@jwt_required()
def user_logout():
    jwt=get_jwt()["jti"]
    tokenBlocked=TokenBlockedList(jti=jwt)
    db.session.add(tokenBlocked)
    db.session.commit()
    return jsonify ({"msg": "Token revoked"})


@api.route('/register', methods=['POST'])
def user_create():
    data=request.get_json()
    print(data)
    new_user=User.query.filter_by(email=data["email"], password=data["password"], is_active=True)
    User.query.filter_by(email=data["email"]).first()
    if (new_user is not None):
        return jsonify({
            "msg": "Email registrado"

        }), 400
    secure_password=bcrypt.generate_password_hash(
        data["password"], rounds=None).decode("utf-8")
    new_user=User(email=data ["email"], password=secure_password, is_active=True)
    print(new_user)
    new_user = User(
        email=data["email"],
        password=secure_password,
        is_active=True,
        first_name=data["first_name"],
        last_name=data["last_name"],
        birth_day=data["birth_day"],
        birth_month=data["birth_month"],
        birth_year=data["birth_year"],
        gender=data["gender"],
        phone=data["phone"],
        suscription=data["suscription"]
    )
    db.session.add(new_user)
    db.session.commit()
    return jsonify(new_user.serialize()), 201

@api.route('/changepassword', methods = ['POST'])
@jwt_required()
def change_password():
    new_password=request.json.get("password")
    user_id=get_jwt_identity()
    secure_password=bcrypt.generate_password_hash(new_password, rounds=None).decode("utf-8")
    user=User.query.get(user_id)
    user.password=secure_password
    db.session.add(user)
    db.session.commit()
    return jsonify({"msg": "Clave actualizada"})

@api.route('/recoverypassword', methods=['POST'])
def recovery_password():
    user_email=request.json.get("email")
    user=User.query.filter_by(email=user_email).first()
    if (user is None):
        return jsonify({"message": "user not found"}),401
    # Generar el token temporal para el cmbio de clave
    access_token= create_access_token(identity=user.id, additional_claims={"type": "password"})
    return jsonify({"recoveryToken": access_token})
    # Enviar el token via email para el cambio de clave

    

@api.route('/helloprotected', methods=['GET'])
@jwt_required()
def hello_protected_get():
    user_id=get_jwt_identity()
    return jsonify({
        "user_id": user_id,
        "message": "Hello protected route"

    })

@api.route('/restaurant', methods=['GET'])
def get_restaurants():
    restaurants= Restaurant(name="McDonalds", platos="Hamburguesa", ubicaciones="Colombia")
    db.session.add(restaurants)
    restaurants1= Restaurant(name="Burger King", platos="Hamburguesa", ubicaciones="Colombia")
    db.session.add(restaurants1)
    restaurants2= Restaurant(name="Wendys", platos="Hamburguesa", ubicaciones="Colombia")
    db.session.add(restaurants2)
    db.session.commit()
    return "ok"




@api.route('/hello', methods=['POST', 'GET'])
def handle_hello():

    response_body = {
        "message": "Hello! I'm a message that came from the backend, check the network tab on the google inspector and you will see the GET request"
    }

    return jsonify(response_body), 200

@api.route('/registerrestaurant', methods=['POST'])
def register_restaurant():
    name=request.json.get("name")
    url=request.json.get("url")
    ubicaciones=request.json.get("ubicaciones")
    new_restaurant=Restaurant(name=name, url=url, ubicaciones=ubicaciones)
    db.session.add(new_restaurant)
    db.session.commit()
    response={"msg": "Restaurante creado exitosamente"}
    return jsonify(response), 200


@api.route('/createRecipeChatGPT', methods=['GET'])
def generateChatResponse():
    prompt = request.json.get("prompt")
    response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": "Create a diet plan with the following characteristics" + prompt }
            ]
        )
    try:
        answer = response['choices'][0]['message']['content'].replace('\n', '<br>')
    except:
        answer = 'Oops you beat the AI, try a different question, if the problem persists, come back later.'
    return answer