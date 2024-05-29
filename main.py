from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import pyodbc
import uuid
from flask_swagger_ui import get_swaggerui_blueprint

app = Flask(__name__)

# Database configuration
DB_CONFIG = {
    'DRIVER': '{ODBC Driver 17 for SQL Server}',
    'SERVER': 'localhost',
    'DATABASE': 'Test_Python',
    'Trusted_Connection': 'yes',
}


def get_db_connection():
    conn_str = (
        f"DRIVER={DB_CONFIG['DRIVER']};"
        f"SERVER={DB_CONFIG['SERVER']};"
        f"DATABASE={DB_CONFIG['DATABASE']};"
        f"Trusted_Connection={DB_CONFIG['Trusted_Connection']};"
    )
    return pyodbc.connect(conn_str)


# Swagger configuration
SWAGGER_URL = '/swagger'
API_URL = '/static/swagger.json'
SWAGGERUI_BLUEPRINT = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={'app_name': "Employee Management API"}
)
app.register_blueprint(SWAGGERUI_BLUEPRINT, url_prefix=SWAGGER_URL)


@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM TUsers WHERE Email = ? AND Password = ?", (email, password))
    user = cursor.fetchone()

    if user:
        token = str(uuid.uuid4())
        expiration = datetime.now() + timedelta(minutes=5)
        cursor.execute("UPDATE TUsers SET Token = ?, DataOraScadenzaToken = ? WHERE Email = ?",
                       (token, expiration, email))
        conn.commit()
        return jsonify({'token': token}), 200
    else:
        return jsonify({'error': 'Invalid credentials'}), 401


def verify_token(token):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM TUsers WHERE Token = ? AND DataOraScadenzaToken > ?", (token, datetime.now()))
    user = cursor.fetchone()
    return user


@app.route('/search_employee', methods=['GET'])
def search_employee():
    token = request.headers.get('Authorization')
    search_text = request.args.get('search_text')

    user = verify_token(token)
    if user:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM TDipendenti WHERE Nome LIKE ? OR Cognome LIKE ? OR id LIKE ?",
                       (f'%{search_text}%', f'%{search_text}%', f'%{search_text}%'))
        employees = cursor.fetchall()

        results = []
        for emp in employees:
            results.append({
                'id': emp.id,
                'Nome': emp.Nome,
                'Cognome': emp.Cognome,
                'DataNascita': emp.DataNascita,
                'ComuneNascita': emp.ComuneNascita,
                'ProvinciaNascita': emp.ProvinciaNascita,
                'Sesso': emp.Sesso,
                'CodiceFiscale': emp.CodiceFiscale
            })
        return jsonify({'employees': results, 'message': 'Operation successful'}), 200
    else:
        return jsonify({'error': 'Invalid or expired token'}), 401


@app.route('/insert_employee', methods=['POST'])
def insert_employee():
    token = request.headers.get('Authorization')
    data = request.json

    user = verify_token(token)
    if user:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO TDipendenti (Nome, Cognome, DataNascita, ComuneNascita, ProvinciaNascita, Sesso) VALUES (?, ?, ?, ?, ?, ?)",
            (data['Nome'], data['Cognome'], data['DataNascita'], data['ComuneNascita'], data['ProvinciaNascita'],
             data['Sesso']))
        conn.commit()
        return jsonify({'message': 'Employee inserted successfully'}), 200
    else:
        return jsonify({'error': 'Invalid or expired token'}), 401


@app.route('/modify_employee', methods=['POST'])
def modify_employee():
    token = request.headers.get('Authorization')
    data = request.json

    id = data.get('id')

    user = verify_token(token)
    if user:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch the employee using composite key (Nome, Cognome, DataNascita)
        cursor.execute("SELECT * FROM TDipendenti WHERE id = ?",
                       (id))
        employee = cursor.fetchone()

        if employee:
            cursor.execute(
                """
                UPDATE TDipendenti 
                SET Nome = ?, Cognome = ?, DataNascita = ?, ComuneNascita = ?, 
                    ProvinciaNascita = ?, Sesso = ? 
                WHERE id = ?
                """,
                (data['Nome'], data['Cognome'], data['DataNascita'], data['ComuneNascita'],
                 data['ProvinciaNascita'], data['Sesso'],
                 id)
            )
            conn.commit()
            return jsonify({'message': 'Employee updated successfully'}), 200
        else:
            return jsonify({'error': 'Employee with specified details does not exist'}), 404
    else:
        return jsonify({'error': 'Invalid or expired token'}), 401


@app.route('/delete_employee', methods=['DELETE'])
def delete_employee():
    token = request.headers.get('Authorization')
    id = request.args.get('id')

    user = verify_token(token)
    if user:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch the employee using composite key (Nome, Cognome, DataNascita)
        cursor.execute("SELECT * FROM TDipendenti WHERE id = ?",
                       (id))
        employee = cursor.fetchone()

        if employee:
            cursor.execute("DELETE FROM TDipendenti WHERE id = ?",
                           (id))
            conn.commit()
            return jsonify({'message': 'Employee deleted successfully'}), 200
        else:
            return jsonify({'error': 'Employee with specified details does not exist'}), 404
    else:
        return jsonify({'error': 'Invalid or expired token'}), 401


@app.route('/calculate_tax_code_by_id', methods=['GET'])
def calculate_tax_code_by_id():
    token = request.headers.get('Authorization')
    id = request.args.get('id')
    user = verify_token(token)
    if user:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM TDipendenti where id = ?", (id))
        employees = cursor.fetchall()

        for emp in employees:
            codice_fiscale = calcolaCodiceFiscale(
                emp.Cognome, emp.Nome, emp.ComuneNascita, emp.ProvinciaNascita,
                emp.Sesso, emp.DataNascita.day, emp.DataNascita.month, emp.DataNascita.year
            )
            cursor.execute(
                "UPDATE TDipendenti SET CodiceFiscale = ? WHERE id = ?",
                (codice_fiscale, emp.id)
            )
        conn.commit()
        return jsonify({'message': 'Tax codes calculated and saved successfully'}), 200
    else:
        return jsonify({'error': 'Invalid or expired token'}), 401

@app.route('/calculate_tax_code', methods=['GET'])
def calculate_tax_code():
    token = request.headers.get('Authorization')

    user = verify_token(token)
    if user:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM TDipendenti")
        employees = cursor.fetchall()

        for emp in employees:
            codice_fiscale = calcolaCodiceFiscale(
                emp.Cognome, emp.Nome, emp.ComuneNascita, emp.ProvinciaNascita,
                emp.Sesso, emp.DataNascita.day, emp.DataNascita.month, emp.DataNascita.year
            )
            cursor.execute(
                "UPDATE TDipendenti SET CodiceFiscale = ? WHERE Nome = ? AND Cognome = ? AND DataNascita = ?",
                (codice_fiscale, emp.Nome, emp.Cognome, emp.DataNascita)
            )

        conn.commit()
        return jsonify({'message': 'Tax codes calculated and saved successfully'}), 200
    else:
        return jsonify({'error': 'Invalid or expired token'}), 401

def solo_consonanti(testo):
    consonanti = ""
    for carattere in testo:
        if carattere.isalpha() and carattere.lower() not in 'aeiou':
            consonanti += carattere
    return consonanti


def switch_caseMese(valore):
    return {
        '01': 'A', '02': 'B', '03': 'C', '04': 'D',
        '05': 'E', '06': 'H', '07': 'L', '08': 'M',
        '09': 'P', '10': 'R', '11': 'S', '12': 'T'
    }.get(valore, 'default')


def fixNome(nome):
    consonantiNome = solo_consonanti(nome.upper())
    if len(consonantiNome) > 3:
        consonantiNome = consonantiNome[:1] + consonantiNome[2:4]
        return consonantiNome
    elif len(consonantiNome) == 3:
        return consonantiNome[:3]
    else:
        return nome[:3]


def calcola_codice_controllo(codice_fiscale):
    valori_dispari = {
        '0': 1, '1': 0, '2': 5, '3': 7, '4': 9, '5': 13, '6': 15, '7': 17,
        '8': 19, '9': 21, 'A': 1, 'B': 0, 'C': 5, 'D': 7, 'E': 9, 'F': 13,
        'G': 15, 'H': 17, 'I': 19, 'J': 21, 'K': 2, 'L': 4, 'M': 18, 'N': 20,
        'O': 11, 'P': 3, 'Q': 6, 'R': 8, 'S': 12, 'T': 14, 'U': 16, 'V': 10,
        'W': 22, 'X': 25, 'Y': 24, 'Z': 23
    }
    valori_pari = {
        '0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7,
        '8': 8, '9': 9, 'A': 0, 'B': 1, 'C': 2, 'D': 3, 'E': 4, 'F': 5,
        'G': 6, 'H': 7, 'I': 8, 'J': 9, 'K': 10, 'L': 11, 'M': 12, 'N': 13,
        'O': 14, 'P': 15, 'Q': 16, 'R': 17, 'S': 18, 'T': 19, 'U': 20,
        'V': 21, 'W': 22, 'X': 23, 'Y': 24, 'Z': 25
    }
    somma = 0
    for i in range(15):
        if i % 2 == 0:
            somma += valori_dispari.get(codice_fiscale[i], 0)
        else:
            somma += valori_pari.get(codice_fiscale[i], 0)
    control_code = chr((somma % 26) + ord('A'))
    return control_code


def get_codice_catastale(comune, provincia):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT [CODICE CATASTALE] FROM codiciCatastali WHERE LOWER(COMUNE) = ? AND LOWER(PROVINCIA) = ?",
                   (comune.lower(), provincia.lower()))
    result = cursor.fetchone()
    return result[0] if result else "XXX"


def calcolaCodiceFiscale(cognome, nome, luogoNascita, provincia, sesso, giorno, mese, anno):
    cognome = solo_consonanti(cognome.strip().upper())[:3]
    nome = fixNome(nome.strip().upper())
    luogoNascita = luogoNascita.strip()
    provincia = provincia.strip().upper()
    sesso = sesso.strip().lower()
    giorno = str(giorno).zfill(2)
    mese = str(mese).zfill(2)
    anno = str(anno).strip()

    codiceLuogoNascita = get_codice_catastale(luogoNascita, provincia)

    if not cognome or not nome or not luogoNascita or not provincia or sesso == "Seleziona" or not giorno or not mese or not anno:
        return

    if len(provincia) != 2:
        return

    cognome = cognome.upper()
    nome = fixNome(nome.upper())
    letteraMese = switch_caseMese(mese)
    codiceSesso = giorno if sesso.upper() == "M" else str(int(giorno) + 40)

    # Ensure components are correct length
    if len(cognome) < 3: cognome = cognome.ljust(3, 'X')
    if len(nome) < 3: nome = nome.ljust(3, 'X')

    codiceFiscale = cognome[:3] + nome + anno[2:4] + letteraMese + codiceSesso + codiceLuogoNascita

    codiceControllo = calcola_codice_controllo(codiceFiscale)
    codiceFiscale += codiceControllo

    return codiceFiscale


if __name__ == "__main__":
    app.run(debug=True)
