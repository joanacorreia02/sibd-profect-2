#!/usr/bin/python3
# Copyright (c) BDist Development Team
# Distributed under the terms of the Modified BSD License.
import os
from logging.config import dictConfig
from datetime import datetime, timedelta

import psycopg
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from psycopg.rows import namedtuple_row
from psycopg.errors import UniqueViolation

# postgres://{user}:{password}@{hostname}:{port}/{database-name}
DATABASE_URL = "postgres://db:db@postgres/db"

dictConfig(
    {
        "version": 1,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] %(levelname)s in %(module)s:%(lineno)s - %(funcName)20s(): %(message)s",
            }
        },
        "handlers": {
            "wsgi": {
                "class": "logging.StreamHandler",
                "stream": "ext://flask.logging.wsgi_errors_stream",
                "formatter": "default",
            }
        },
        "root": {"level": "INFO", "handlers": ["wsgi"]},
    }
)

app = Flask(__name__)
app.config.from_prefixed_env()
log = app.logger

@app.route("/", methods=("GET",))

def homepage():
    return render_template("homepage.html")



@app.route("/search_clients", methods=("GET","POST"))
def search_clients():
    """Show all the clients, alphabetical order."""
    
    vat = request.form.get('vat') if request.form.get('vat') else 'MISSING'
    name = request.form.get('name') if request.form.get('name') else 'MISSING'
    city = request.form.get('city') if request.form.get('city') else 'MISSING'
    zip_code = request.form.get('zip') if request.form.get('zip') else 'MISSING'
    street = request.form.get('street') if request.form.get('street') else 'MISSING'
    
    if vat != 'MISSING' or name != 'MISSING' or city != 'MISSING' or zip_code != 'MISSING' or street != 'MISSING':
        
        with psycopg.connect(conninfo=DATABASE_URL) as conn:
            with conn.cursor(row_factory=namedtuple_row) as cur:
                clients = cur.execute(
                    """
                    SELECT name, VAT
                    FROM client 
                    WHERE     
                        (name LIKE %(name)s OR %(name_na)s = 'MISSING' ) AND 
                        (vat = %(vat)s OR %(vat)s ='MISSING') AND 
                        (city LIKE %(city)s OR %(city_na)s = 'MISSING') AND 
                        (street LIKE %(street)s OR %(street_na)s = 'MISSING') AND
                        (zip LIKE %(zip)s OR %(zip_na)s = 'MISSING')
                    ORDER BY name ASC;
                    """,
                    {
                        "vat": vat,
                        "name": f'%{name}%',
                        "city": f'%{city}%',
                        "street": f'%{street}%',
                        "zip": f'%{zip_code}%',
                        "name_na": name,
                        "street_na": street,
                        "zip_na": zip_code,
                        "city_na": city,
                    },
                ).fetchall()
                log.debug(f"Found {cur.rowcount} rows.")

        if len(clients)>0:
            return render_template("search_clients.html", vat=vat,clients=clients)
        else:
            flash("No clients found.") 
    else:
        flash("No values inserted.") 
    return render_template("search_clients.html")




@app.route("/new_client", methods=("GET", "POST"))
def new_client():
    VAT = request.form.get('VAT')
    name = request.form.get('name')
    birth_date = request.form.get('birth_date')
    street = request.form.get('street')
    city = request.form.get('city')
    zip = request.form.get('zip')
    gender = request.form.get('gender')

    new_client = None  # Initialize new_client outside the try block

    try:
        with psycopg.connect(conninfo=DATABASE_URL) as conn:
            with conn.cursor(row_factory=namedtuple_row) as cur:
                new_client = cur.execute(
                    """
                    INSERT INTO client 
                    VALUES (%(VAT)s, %(name)s, %(birth_date)s, %(street)s, %(city)s, %(zip)s, %(gender)s) 
                    RETURNING *;  -- Return the inserted row
                    """,
                    {"VAT": VAT, "name": name, "birth_date": birth_date, "street": street, "city": city, "zip": zip,
                        "gender": gender},
                ).fetchone()
                log.debug(f"Found {cur.rowcount} rows.")
        flash("New client added successfully.")
    except UniqueViolation:
        flash("Client already exists")
    except Exception as e:
        flash("Check your inputs. Try again!")
        log.error(str(e))

    return render_template("new_client.html", VAT=VAT, new_client=new_client, name=name, birth_date=birth_date,
                           street=street, city=city, zip=zip, gender=gender)

@app.route("/appointments/<vat>", methods=["GET", "POST"])
def new_appointment(vat):
    # Assuming you have a variable 'doctors' containing the list of doctors for the dropdown

    # with psycopg.connect(conninfo=DATABASE_URL) as conn:
    #     with conn.cursor(row_factory=namedtuple_row) as cur:
    #         doctors = cur.execute(
    #             """
    #             SELECT d.VAT, e.name
    #             FROM doctor d
    #             JOIN employee e on d.VAT = e.VAT;
    #             """
    #         ).fetchall()
            
    if request.method == "POST":
        date = request.form.get('date')
        time = request.form.get('time')
        doctor_vat = request.form.get('doctorvat')
        description = request.form.get('description')

        appointment_datetime = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        start_time = appointment_datetime - timedelta(hours=1)
        end_time = appointment_datetime + timedelta(hours=1)
        
        with psycopg.connect(conninfo=DATABASE_URL) as conn:
            with conn.cursor(row_factory=namedtuple_row) as cur:
                # Check for overlapping appointments for the selected doctor
                doc = cur.execute(
                    """
                    SELECT *
                    FROM doctor
                    WHERE VAT = %(doctor_vat)s
                    """,
                    {"doctor_vat": doctor_vat}
                ).fetchall()
        
        if  doc:
            with psycopg.connect(conninfo=DATABASE_URL) as conn:
                with conn.cursor(row_factory=namedtuple_row) as cur:
                    # Check for overlapping appointments for the selected doctor
                    overlapping_appointments = cur.execute(
                        """
                        SELECT d.VAT, e.name AS doctor_name
                        FROM appointment a
                        JOIN doctor d ON a.VAT_doctor = d.VAT
                        JOIN employee e ON e.VAT = d.VAT
                        WHERE d.VAT = %(doctor_vat)s AND date_timestamp BETWEEN %(start_time)s AND %(end_time)s;
                        """,
                        {"doctor_vat": doctor_vat, "start_time": start_time, "end_time": end_time}
                    ).fetchall()

            if overlapping_appointments:
                flash("Overlapping appointments for the selected doctor. Choose a different time.")
            else:
                # Insert the new appointment into the 'appointment' table
                
                flash(doctor_vat)
                with psycopg.connect(conninfo=DATABASE_URL) as conn:
                    with conn.cursor(row_factory=namedtuple_row) as cur:
                        cur.execute(
                            """
                            INSERT INTO appointment (date_timestamp, VAT_doctor, VAT_client, description)
                            VALUES (%(appointment_datetime)s, %(doctor_vat)s, %(vat)s, %(description)s);
                            """,
                            {
                                "appointment_datetime": appointment_datetime,
                                "doctor_vat": doctor_vat,
                                "vat": vat,
                                "description": description,
                            }
                        )
                        conn.commit()
                
                flash("New appointment registered successfuly!")
                return render_template("new_appointment.html",VAT=vat)
        else:
            flash("Incorrect Doctor VAT inserted")
            return render_template("new_appointment.html")
        
    return render_template("new_appointment.html")

@app.route("/available_doctors", methods=["GET", "POST"])
def available_doctors():
    if request.method == "POST":
        date = request.form.get('date')
        time = request.form.get('time')

        selected_datetime = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        start_time = selected_datetime - timedelta(hours=1)
        end_time = selected_datetime + timedelta(hours=1)

        # Query the database to find available doctors for the selected date and time
        with psycopg.connect(conninfo=DATABASE_URL) as conn:
            with conn.cursor(row_factory=namedtuple_row) as cur:
                available_doctors = cur.execute(
                    """
                    SELECT d.VAT, e.name
                    FROM doctor d
                    JOIN employee e on d.VAT = e.VAT
                    WHERE d.VAT NOT IN (
                        SELECT a.VAT_doctor
                        FROM appointment a
                        WHERE date_timestamp BETWEEN %(start_time)s AND %(end_time)s
                    );
                    """,
                    {"start_time": start_time, "end_time": end_time}
                ).fetchall()

        return render_template("available_doctors.html", date=date, time=time, available_doctors=available_doctors)

    return render_template("available_doctors.html")

@app.route("/client/<vat>/appointments", methods=["GET"])
def client_appointments(vat):
    # Query the database to retrieve detailed information about appointments for the selected client
    current_time = datetime.now()

    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            appointments = cur.execute(
                """
                SELECT
                    a.date_timestamp,
                    e.name AS doctor_name,
                    a.VAT_doctor as vat_doctor,
                    a.description,
                    CASE
                        WHEN c.date_timestamp IS NOT NULL THEN 'Attended'
                        WHEN a.date_timestamp > %(current_time)s THEN 'Scheduled'
                        ELSE 'Not Attended'
                    END AS attended
                FROM appointment a
                JOIN employee e ON e.VAT = a.VAT_doctor
                LEFT JOIN doctor d ON a.VAT_doctor = d.VAT
                LEFT JOIN consultation c ON a.date_timestamp = c.date_timestamp  AND a.VAT_doctor = c.VAT_doctor
                WHERE a.VAT_client = %(vat)s
                ORDER BY a.date_timestamp DESC;
                """,
                {"vat": vat, "current_time": current_time}
            ).fetchall()

    return render_template("client_appointments.html", vat=vat, appointments=appointments)


@app.route("/consultation_details/<vat_doctor>/<string:consultation_date>")
def consultation_details(vat_doctor, consultation_date):
    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            soap_notes = cur.execute(
                """
                SELECT SOAP_S, SOAP_O, SOAP_A, SOAP_P
                FROM consultation
                WHERE VAT_doctor = %(vat_doctor)s AND date_timestamp = %(date_timestamp)s;
                """,
                {"vat_doctor": vat_doctor, "date_timestamp": consultation_date}
            ).fetchall()

    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            nurses = cur.execute(
                """
                SELECT e.name AS nurse_name
                FROM consultation_assistant ca
                JOIN employee e ON e.VAT = ca.VAT_nurse
                WHERE ca.VAT_doctor = %(vat_doctor)s AND ca.date_timestamp = %(date_timestamp)s;
                """,
                {"vat_doctor": vat_doctor, "date_timestamp": consultation_date}
            ).fetchall()


    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            diagnostic_codes = cur.execute(
                """
                SELECT d.ID, d.description
                FROM consultation_diagnostic cd
                JOIN diagnostic_code d ON cd.ID = d.ID
                WHERE cd.VAT_doctor = %(vat_doctor)s AND cd.date_timestamp = %(date_timestamp)s;
                """,
                {"vat_doctor": vat_doctor, "date_timestamp": consultation_date}
            ).fetchall()

    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            prescriptions = cur.execute(
                """
                SELECT m.name, m.lab, cd.dosage, cd.description
                FROM prescription cd
                JOIN medication m ON cd.name = m.name AND cd.lab = m.lab
                WHERE cd.VAT_doctor = %(vat_doctor)s AND cd.date_timestamp = %(date_timestamp)s;
                """,
                {"vat_doctor": vat_doctor, "date_timestamp": consultation_date}
            ).fetchall()

    return render_template(
        "consultation_details.html",
        vat_doctor=vat_doctor,
        consultation_date=consultation_date,
        soap_notes=soap_notes,
        nurses=nurses,
        diagnostic_codes=diagnostic_codes,
        prescriptions=prescriptions,
    )
    
@app.route("/new_consultation_soap/<vat_doctor>/<string:consultation_date>", methods=["GET", "POST"])
def new_consultation_soap(vat_doctor, consultation_date):
    if request.method == "POST":
        # Handle SOAP notes insertion here
        soap_s = request.form.get('soap_s')
        soap_o = request.form.get('soap_o')
        soap_a = request.form.get('soap_a')
        soap_p = request.form.get('soap_p')

        with psycopg.connect(conninfo=DATABASE_URL) as conn:
            with conn.cursor(row_factory=namedtuple_row) as cur:
                cur.execute(
                    """
                    INSERT INTO consultation (VAT_doctor, date_timestamp, SOAP_S, SOAP_O, SOAP_A, SOAP_P)
                    VALUES (%s, %s, %s, %s, %s, %s);
                    """,
                    (vat_doctor, consultation_date, soap_s, soap_o, soap_a, soap_p)
                )
                conn.commit()
        return redirect(url_for('new_consultation_nurse', vat_doctor = vat_doctor, consultation_date = consultation_date))
                
    return render_template("new_consultation_soap.html", vat_doctor = vat_doctor, consultation_date = consultation_date)

@app.route("/new_consultation_nurse/<vat_doctor>/<string:consultation_date>", methods=["GET", "POST"])
def new_consultation_nurse(vat_doctor, consultation_date):
    # Fetch all nurses from the database
    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute(
                """
                SELECT n.VAT, e.name
                FROM nurse n 
                JOIN employee e ON e.VAT = n.VAT
                WHERE n.VAT NOT IN (
                    SELECT VAT_nurse
                    FROM consultation_assistant
                    WHERE VAT_doctor = %(vat_doctor)s AND date_timestamp = %(consultation_date)s
                );
                """,
                {"vat_doctor": vat_doctor, "consultation_date": consultation_date}
            )
            nurses = cur.fetchall()

    if request.method == "POST":
        vat_nurse = request.form.get('input_nurse_vat')

        with psycopg.connect(conninfo=DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM consultation_assistant
                    WHERE VAT_doctor = %(vat_doctor)s AND VAT_nurse = %(vat_nurse)s AND date_timestamp = %(consultation_date)s
                    """,
                    {"vat_doctor": vat_doctor, "vat_nurse": vat_nurse, "consultation_date": consultation_date}
                )
                already_assist = cur.fetchone()

                if already_assist:
                    flash("That nurse is already registered as assisting that consultation")
                elif vat_nurse in [n.vat for n in nurses]:
                    cur.execute(
                        """
                        INSERT INTO consultation_assistant (VAT_doctor, date_timestamp, VAT_nurse)
                        VALUES (%s, %s, %s);
                        """,
                        (vat_doctor, consultation_date, vat_nurse)
                    )
                    conn.commit()

                    flash(f"Nurse with VAT {vat_nurse} successfully registered as assisting in the consultation!")
                else:
                    flash("The following VAT does not correspond to a nurse.")

    return render_template("new_consultation_nurse.html", vat_doctor=vat_doctor, consultation_date=consultation_date, nurses=nurses)

@app.route("/new_consultation_diagnostic/<vat_doctor>/<string:consultation_date>", methods=["GET", "POST"])
def new_consultation_diagnostic(vat_doctor, consultation_date):

    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute(
                """
                SELECT description
                FROM diagnostic_code
                """
            )
            diagnostic_list = cur.fetchall()

    if request.method == "POST":
        diagnostic_desc = request.form.get('input_diagnostic')

        with psycopg.connect(conninfo=DATABASE_URL) as conn:
            with conn.cursor(row_factory=namedtuple_row) as cur:
                cur.execute(
                    """
                    SELECT ID, description
                    FROM diagnostic_code 
                    WHERE description = %(diagnostic_desc)s
                    """,
                    {"diagnostic_desc": diagnostic_desc}
                )
                diagnostic = cur.fetchone()

        if  not diagnostic:
            with psycopg.connect(conninfo=DATABASE_URL) as conn:
                with conn.cursor(row_factory=namedtuple_row) as cur:
                    cur.execute("SELECT MAX(ID) FROM diagnostic_code;")
                    max_id = cur.fetchone().max
                    new_id = max_id + 1

                    cur.execute(
                        """
                        INSERT INTO diagnostic_code (ID, description)
                        VALUES (%s, %s);
                        """,
                        (new_id, diagnostic_desc)
                    )
                    conn.commit()
            diagnostic_id = new_id
        
        else:
            diagnostic_id = diagnostic.id

        try:
            with psycopg.connect(conninfo=DATABASE_URL) as conn:
                with conn.cursor(row_factory=namedtuple_row) as cur:
                    cur.execute(
                        """
                        INSERT INTO consultation_diagnostic (VAT_doctor, date_timestamp, ID)
                        VALUES (%s, %s, %s);
                        """,
                        (vat_doctor, consultation_date,diagnostic_id)
                    )
                    conn.commit()
            return redirect(url_for('new_consultation_prescription', diagnostic_id=diagnostic_id, vat_doctor=vat_doctor, consultation_date=consultation_date))
        except UniqueViolation:
            flash("The insert diagnostic, has already been inserted.")
            
        except:
            flash("Something went wrong. Try to refresh the page or return to the previous step and repeat.")
            
    return render_template("new_consultation_diagnostic.html", vat_doctor=vat_doctor, consultation_date=consultation_date, diagnostic_list= diagnostic_list)


@app.route("/new_consultation_prescription/<int:diagnostic_id>/<vat_doctor>/<string:consultation_date>", methods=["GET", "POST"])
def new_consultation_prescription(diagnostic_id, vat_doctor, consultation_date):
    # Fetch med lab pairs from the database
    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute(
                """
                SELECT name, lab
                FROM medication
                """
            )
            med_lab_list = cur.fetchall()

    if request.method == "POST":
        name = request.form.get('med_name')
        lab = request.form.get('med_lab')
        dosage = request.form.get('dosage')
        description = request.form.get('prescription_desc')

        if (name, lab) not in med_lab_list:
            with psycopg.connect(conninfo=DATABASE_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO medication (name, lab)
                        VALUES (%s, %s);
                        """,
                        (name, lab)
                    )
                    conn.commit()

        try:
            with psycopg.connect(conninfo=DATABASE_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO prescription (VAT_doctor, date_timestamp, ID, name, lab, dosage, description)
                        VALUES (%s, %s, %s, %s, %s, %s, %s);
                        """,
                        (vat_doctor, consultation_date, diagnostic_id, name, lab, dosage, description)
                    )
                    conn.commit()
        except UniqueViolation:
            flash("The medication inserted, has already been prescribed for this consultation diagnostic")
            
        except:
            flash("Something went wrong. Try to refresh the page or return to the previous step and repeat.")
            
    return render_template("new_consultation_prescription.html", diagnostic_id=diagnostic_id, vat_doctor=vat_doctor, consultation_date=consultation_date, med_lab_list=med_lab_list)

@app.route("/dashboard", methods=["GET", "POST"])
def consultations_data():
    if request.method == "GET":
         try:
             with psycopg.connect(conninfo=DATABASE_URL) as conn:
                with conn.cursor(row_factory=namedtuple_row) as cur:
                    consultations_data = cur.execute(
                        """
                        SELECT *
                        FROM facts_consultations 
                        """
                    ).fetchall()
         except psycopg2.Error as e:
             print(f"Database error: {e}")

    return render_template('dashboard.html', consultations_data=consultations_data)

def get_consultations_between_dates(start_date, end_date):

    start_date_str = request.form['start_date']
    end_date_str = request.form['end_date']

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

    if request.method=="POST":
        try:
        
            with psycopg.connect(conninfo=DATABASE_URL) as conn:
                with conn.cursor(row_factory=namedtuple_row) as cur:
                     consults_by_interval = cur.execute(
                         """
                        SELECT *
                        FROM facts_consultations
                        WHERE date BETWEEN %s AND %s
                        """,
                        (start_date, end_date)
                     ).fetchall()
                 
            

        except psycopg2.Error as e:
            print(f"Database error: {e}")
        finally:
            if conn:
                conn.close()
    return render_template('dashboard.html', consults_by_interval=consults_by_interval)

   

def total_consultations():
    if request.method == "GET":
        try:
            with psycopg.connect(conninfo=DATABASE_URL) as conn:
                with con.cursor(row_factory=namedtuple_row)as cur:
                    total_consultations=cur.execute(
                        """ 
                        SELECT COUNT(*) as total_consultations 
                        FROM facts_consultations
                        """
                     ).fetchall()
            
        except psycopg2.Error as e:
            print(f"Database error: {e}")
                
    return render_template('dashboard.html', total_consultations=total_consultations)

def consults_by_client():
    if request.method == "GET":
        try:
            with psycopg2.connect(conninfo=DATABASE_URL) as conn:
                with connection.cursor(row_factory=namedtuple_row) as cur:
                    consults_by_client = cur.execute(
                        """
                            SELECT VAT,count(*) as total_consultations
                            FROM facts_consultations
                            GROUP BY VAT
                        """
                    ).fetchall()

        except psycopg2.Error as e:
            print(f"Database error: {e}")

        

        return render_template('dashboard.html', consults_by_client=consults_by_client)

def consults_by_year():
    if request.method == "GET":
        try:
            with psycopg2.connect(conninfo=DATABASE_URL) as conn:
                with connection.cursor(row_factory=namedtuple_row) as cur:
                    consults_by_year = cur.execute(
                        """
                            SELECT Extract(YEAR FROM date) as year ,COUNT(*) as total_consultations 
                            FROM facts_consultations
                            GROUP BY Extract(YEAR FROM date)
                            ORDER BY Extract(YEAR FROM date)
                        """
                    ).fetchall()

        except psycopg2.Error as e:
            print(f"Database error: {e}")

        

        return render_template('dashboard.html', consults_by_year=consults_by_year)
                    

if __name__ == "__main__":
    app.run()