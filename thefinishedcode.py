import tkinter as tk
from tkinter import messagebox
import threading
import numpy as np
from tkinter import Canvas
import sqlite3
import datetime
from queue import Queue
import time
import serial

# DatabaseHandler class for database operations
class DatabaseHandler:
    def __init__(self, db_name='patient_data11.db'):
        self.db_name = db_name
        self.create_patient_table()

    def get_connection(self):
        return sqlite3.connect(self.db_name)

    def create_patient_table(self):
        try:
            conn = self.get_connection()
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS patients (
                           id INTEGER PRIMARY KEY,
                           name TEXT NOT NULL,
                           age INTEGER,
                           cpr TEXT UNIQUE)''')
            conn.commit()
            conn.close()
            print("Patient table created.")
        except sqlite3.Error as e:
            print("Error creating patient table:", e)

    def insert_patient(self, name, age, cpr):
        try:
            conn = self.get_connection()
            c = conn.cursor()
            c.execute("INSERT INTO patients (name, age, cpr) VALUES (?, ?, ?)", (name, age, cpr))
            conn.commit()
            conn.close()
            print("Patient info inserted successfully.")
        except sqlite3.Error as e:
            print("Error inserting patient info:", e)

    def create_patient_ekg_data_table(self, cpr):
        table_name = f"ekg_data_{cpr.replace(' ', '_').replace('-', '')}"
        try:
            conn = self.get_connection()
            c = conn.cursor()
            c.execute(f'''CREATE TABLE IF NOT EXISTS {table_name} (
                           date TEXT PRIMARY KEY,
                           electrical_signals_of_the_heart REAL)''')
            conn.commit()
            conn.close()
            print(f"Patient data table for {cpr} created successfully.")
        except sqlite3.Error as e:
            print("Error creating data table:", e)

    def insert_patient_ekg_data(self, cpr, ekg_data):
        table_name = f"ekg_data_{cpr.replace(' ', '_').replace('-', '')}"
        try:
            conn = self.get_connection()
            c = conn.cursor()
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            c.execute(f"INSERT INTO {table_name} (date, electrical_signals_of_the_heart) VALUES (?, ?)",
                      (current_time, ekg_data))
            conn.commit()
            conn.close()
            print(f"Patient data inserted successfully: {ekg_data} at {current_time}")
        except sqlite3.Error as e:
            print("Error inserting data into table:", e)


# Calculate heart rate
def calculate_heart_rate(ekg_data, sampling_rate):
    # Initialiser variabler til at spore minimums- og maksimumsværdier
    max_val = max_first_derivative = max_second_derivative = float('-inf')
    min_val = min_first_derivative = min_second_derivative = float('inf')

    previous_val = prev_first_derivative = prev_second_derivative = 0

    # Initialiser heart_rate
    heart_rate = 0

    # Iterer over dataene for at beregne minimums- og maksimumsværdier
    for index in range(len(ekg_data)):
        current_val = ekg_data[index]
        current_first_derivative = current_val - previous_val
        current_second_derivative = current_first_derivative - prev_first_derivative

        max_val = max(max_val, current_val)
        min_val = min(min_val, current_val)

        if index > 0:
            max_first_derivative = max(max_first_derivative, current_first_derivative)
            min_first_derivative = min(min_first_derivative, current_first_derivative)

        if index > 1:
            max_second_derivative = max(max_second_derivative, current_second_derivative)
            min_second_derivative = min(min_second_derivative, current_second_derivative)

        previous_val, prev_first_derivative, prev_second_derivative = current_val, current_first_derivative, current_second_derivative

    print("y:", min_val, max_val)
    print("y':", min_first_derivative, max_first_derivative)
    print("y'':", min_second_derivative, max_second_derivative)
    print("-")

    # Initialiser parametre for beregning af hjertefrekvens
    time_index = time_interval = cumulative_x = cumulative_heart_rate = previous_val = prev_first_derivative = prev_second_derivative = 0
    falling_edge_detected = False
    smoothing = 0.20
    threshold = min_second_derivative / 3

    # Behandl dataene for at estimere hjertefrekvens
    for index in range(len(ekg_data)):
        current_val = ekg_data[index]
        current_first_derivative = current_val - previous_val
        current_second_derivative = current_first_derivative - prev_first_derivative

        if index > 2:
            if prev_second_derivative < threshold and current_second_derivative > prev_second_derivative:
                falling_edge_detected = True
                print(f"Faldende kant detekteret ved index {index} med anden afledte {current_second_derivative}")

            if prev_second_derivative > threshold and falling_edge_detected:
                time_interval = index - time_index
                time_index = index
                falling_edge_detected = False
                heart_rate = round(sampling_rate * 60 / time_interval)

                if cumulative_x == 0:
                    max_heart_rate = heart_rate
                else:
                    max_heart_rate = (1 - smoothing) * max_heart_rate + smoothing * heart_rate

                cumulative_x += 1
                cumulative_heart_rate += heart_rate

                print(f"time_interval: {time_interval}, heart_rate: {heart_rate}, gennemsnitlig hjertefrekvens: {round(cumulative_heart_rate / cumulative_x)}, max_hjertefrekvens: {round(max_heart_rate)}")

        previous_val, prev_first_derivative, prev_second_derivative = current_val, current_first_derivative, current_second_derivative

    if cumulative_x > 0:
        return int(cumulative_heart_rate / cumulative_x)
    return 0



# EKGCanvas class to draw EKG
class EKGCanvas:
    def __init__(self, frame, width, height, sampling_rate, lead_name):
        self.lead_name = lead_name
        self.canvas = Canvas(frame, bg='white', width=width, height=height)
        self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)  # Allow expansion and filling
        self.width = width
        self.height = height
        self.sampling_rate = sampling_rate
        self.start_time = datetime.datetime.now()

        # Add lead name label
        self.lead_label = tk.Label(frame, text=lead_name, font=('Helvetica', 12))
        self.lead_label.pack(side=tk.TOP)

    def draw_ekg(self, ekg_data, max_time, min_signal, max_signal):
        self.canvas.delete("all")
        print(f"Drawing EKG for {self.lead_name} with data range {min_signal} to {max_signal}")

        self.width = self.canvas.winfo_width()
        self.height = self.canvas.winfo_height()

        # Draw grid and axes
        for i in range(0, self.width, 10):  # Minor red lines every 10 pixels
            if i % 50 == 0:  # Thicker red lines every 50 pixels
                self.canvas.create_line([(i, 0), (i, self.height)], tag='grid', fill='red', width=1)
            else:
                self.canvas.create_line([(i, 0), (i, self.height)], tag='grid', fill='red', width=0.5)

        for i in range(0, self.height, 10):  # Minor red lines every 10 pixels
            if i % 50 == 0:  # Thicker red lines every 50 pixels
                self.canvas.create_line([(0, i), (self.width, i)], tag='grid', fill='red', width=1)
            else:
                self.canvas.create_line([(0, i), (self.width, i)], tag='grid', fill='red', width=0.5)

        # Draw x-axis
        self.canvas.create_line(0, self.height // 2, self.width, self.height // 2, fill='black', width=1)
        # Draw y-axis
        self.canvas.create_line(50, 0, 50, self.height, fill='black', width=1)

        if min_signal != max_signal:
            # Labels for y-axis
            for i in range(0, self.height, 50):
                value = (1 - i / self.height) * (max_signal - min_signal) + min_signal
                self.canvas.create_text(25, i, text=f"{value:.2f}", fill="black")

            # Labels for x-axis
            for i in range(50, self.width, 50):
                if (i // 50) % 5 == 0:  # Show only every fifth label
                    time_offset = i / self.width * max_time
                    time_label = (self.start_time + datetime.timedelta(seconds=time_offset)).strftime("%H:%M:%S")
                    self.canvas.create_text(i, self.height - 10, text=time_label, fill="black")

            # Calculate peaks
            threshold = (np.max(ekg_data) + np.min(ekg_data)) / 2
            peaks = [i for i in range(1, len(ekg_data) - 1) if ekg_data[i] > threshold and ekg_data[i - 1] <= threshold]

            for i in range(len(ekg_data) - 1):
                x1 = self.width * (i / self.sampling_rate / max_time)
                y1 = self.height * (1 - (ekg_data[i] - min_signal) / (max_signal - min_signal))
                x2 = self.width * ((i + 1) / self.sampling_rate / max_time)
                y2 = self.height * (1 - (ekg_data[i + 1] - min_signal) / (max_signal - min_signal))
                self.canvas.create_line(x1, y1, x2, y2, fill="black")

            # Draw green dots at peaks
            for peak in peaks:
                x_peak = self.width * (peak / self.sampling_rate / max_time)
                y_peak = self.height * (1 - (ekg_data[peak] - min_signal) / (max_signal - min_signal))
                self.canvas.create_oval(x_peak - 2, y_peak - 2, x_peak + 2, y_peak + 2, fill='green', outline='green')
        else:
            # If min_signal equals max_signal, draw a flat line
            self.canvas.create_line(0, self.height // 2, self.width, self.height // 2, fill='black')


# MeasurementQueue class to handle buffers
class MeasurementQueue:
    def __init__(self, max_size):
        self.queue = Queue(maxsize=max_size)
        self.lock = threading.Lock()
        self.not_empty = threading.Condition(self.lock)

    def append(self, item):
        with self.not_empty:
            while self.queue.full():
                self.not_empty.wait()
            print(f"Appending to queue: {item}")
            self.queue.put(item)
            self.not_empty.notify()

    def get(self):
        with self.not_empty:
            while self.queue.empty():
                self.not_empty.wait()
            item = self.queue.get()
            print(f"Getting from queue: {item}")
            self.not_empty.notify()
        return item

    def size(self):
        with self.lock:
            return self.queue.qsize()


# Read from serial and put data in buffer
def read_from_serial(buffer, queue, serial_port, sampling_rate):
    ser = serial.Serial(serial_port, 9600)  # Open the serial port
    while True:
        if ser.in_waiting > 0:
            line = ser.readline().decode('utf-8').strip()
            try:
                value = float(line)
                buffer.append(value)
                if len(buffer) >= buffer_size:
                    queue.append(buffer[:])
                    buffer.clear()
            except ValueError:
                print(f"Invalid data: {line}")
        time.sleep(1 / sampling_rate)


# Write data from queue to database
def write_to_database(queue, db_name, cpr):
    db_handler = DatabaseHandler(db_name)  # Create database connection
    while True:  # Infinite loop
        buffer = queue.get()  # Get data from queue
        for ekg_data in buffer:
            db_handler.insert_patient_ekg_data(cpr, ekg_data)  # Insert data into database


# EKG_graf class for displaying EKG data and handling print functionality

buffer_size = 5


class EKG_graf:
    def __init__(self, name, age, cpr, duration=10, sampling_rate=300, serial_port='/dev/cu.usbmodem14101'):
        self.name = name
        self.age = age
        self.cpr = cpr
        self.duration = duration
        self.sampling_rate = sampling_rate
        self.ekg_data = []
        self.t = 0
        self.displayed_ekg_data = []
        self.root = tk.Toplevel()  # Use Toplevel instead of Tk
        self.root.title("EKG")
        self.root.geometry("900x800")
        self.root.minsize(900, 800)

        # Frame for patient info and clock
        self.info_frame = tk.Frame(self.root)
        self.info_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        # Patient info label
        self.patient_info_label = tk.Label(self.info_frame, text=f"Name: {name}\nAge: {age}\nCPR: {cpr}",
                                           font=('Helvetica', 12), anchor="w")
        self.patient_info_label.pack(side=tk.LEFT)

        # Real-time clock label
        self.clock_label = tk.Label(self.info_frame, text="", font=('Helvetica', 12), anchor="e")
        self.clock_label.pack(side=tk.RIGHT)
        self.update_clock()

        # Heart rate label
        self.heart_rate_label = tk.Label(self.info_frame, text="Heart Rate: Calculating...", font=('Helvetica', 12),
                                         anchor="e")
        self.heart_rate_label.pack(side=tk.RIGHT, padx=10)

        # Frame for EKG canvas
        self.ekg_frame = tk.Frame(self.root)
        self.ekg_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Create a single EKG canvas
        self.ekg_canvas = EKGCanvas(self.ekg_frame, 900, 600, self.sampling_rate, "Lead I")

        # Add print button
        self.print_button = tk.Button(self.root, text="Udskriv", command=self.open_print_window)
        self.print_button.pack(side=tk.BOTTOM, pady=10)

        # Initialize buffer and queue
        self.buffer = []
        self.queue = MeasurementQueue(max_size=5)

        # Create threads for serial reading, database writing, and graph updating
        self.serial_thread = threading.Thread(target=read_from_serial,
                                              args=(self.buffer, self.queue, serial_port, self.sampling_rate))
        self.database_thread = threading.Thread(target=write_to_database,
                                                args=(self.queue, 'patient_data11.db', self.cpr))
        self.graph_thread = threading.Thread(target=self.update_ekg_from_queue)

        self.serial_thread.start()
        self.database_thread.start()
        self.graph_thread.start()

        # Start clock update
        self.update_clock()

    def update_clock(self):
        now = datetime.datetime.now().strftime("%H:%M:%S %Y-%m-%d")
        self.clock_label.config(text=f"Current Time: {now}")
        self.root.after(1000, self.update_clock)

    def update_ekg_from_queue(self):
        while True:
            time.sleep(0.1)  # Add a delay to reduce the update frequency
            if self.queue.size() > 0:
                buffer = self.queue.get()
                print(f"Data from buffer to be displayed: {buffer}")
                self.displayed_ekg_data.extend(buffer)
                if len(self.displayed_ekg_data) > self.duration * self.sampling_rate:
                    self.displayed_ekg_data = self.displayed_ekg_data[-self.duration * self.sampling_rate:]

                max_time = len(self.displayed_ekg_data) / self.sampling_rate
                min_signal = np.min(self.displayed_ekg_data)
                max_signal = np.max(self.displayed_ekg_data)

                self.ekg_canvas.draw_ekg(self.displayed_ekg_data, max_time, min_signal, max_signal)

                heart_rate = calculate_heart_rate(self.displayed_ekg_data, self.sampling_rate)
                self.heart_rate_label.config(text=f"Heart Rate: {heart_rate} BPM")
                print(f"Updated heart rate: {heart_rate} BPM")  # Debugging information

    def open_print_window(self):
        # Create a new window
        print_window = tk.Toplevel(self.root)
        print_window.title("Udskriv EKG")
        print_window.geometry("900x800")
        print_window.minsize(900, 800)

        # Create a frame for the canvas
        print_frame = tk.Frame(print_window, bd=2, relief=tk.SUNKEN)
        print_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create the EKG canvas in the new window
        ekg_canvas = EKGCanvas(print_frame, 900, 600, self.sampling_rate, "Lead I")

        # Update canvas dimensions before drawing
        print_window.update_idletasks()

        # Draw the EKG data on the new canvas
        max_time = len(self.displayed_ekg_data) / self.sampling_rate
        min_signal = np.min(self.displayed_ekg_data)
        max_signal = np.max(self.displayed_ekg_data)
        ekg_canvas.draw_ekg(self.displayed_ekg_data, max_time, min_signal, max_signal)

    def run(self):
        self.root.mainloop()


# LoginApp class for user login
class LoginApp:
    def __init__(self, root):
        self.root = root
        self.root.geometry('550x550')
        self.root.title("CardioMonitor.dk")

        # Title label
        self.title_label = tk.Label(root, text="CardioMonitor.dk", font=("Helvetica", 20))
        self.title_label.pack(pady=30)

        # Username entry
        self.username_label = tk.Label(root, text="Brugernavn:")
        self.username_label.pack(pady=20)
        self.username_entry = tk.Entry(root)
        self.username_entry.pack(pady=5)

        # Password entry
        self.password_label = tk.Label(root, text="Adgangskode:")
        self.password_label.pack(pady=10)
        self.password_entry = tk.Entry(root, show="*")
        self.password_entry.pack(pady=5)

        # Login button
        self.login_button = tk.Button(root, text="Login", command=self.start_login_thread)
        self.login_button.pack(pady=5)

    def start_login_thread(self):
        # Start login in a separate thread
        threading.Thread(target=self.login).start()

    def login(self):
        try:
            # Validate input length
            brugernavn = self.username_entry.get().strip()
            adgangskode = self.password_entry.get().strip()
            if not brugernavn or not adgangskode:
                messagebox.showerror("Error", "username or password is missing!")
                return

            # Validate username and password
            users = {'Peter': 'Peter123', 'Nanna': 'Nanna123', 'x': 'xx'}
            if brugernavn in users and users[brugernavn] == adgangskode:
                self.on_login_success()
            else:
                messagebox.showerror("Error", "Username or Password invalid, try again please!")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_login_success(self):
        messagebox.showinfo("Success", "Login Successful")
        self.root.after(100, self.open_hovedside)

    def open_hovedside(self):
        self.root.destroy()
        ekg_root = tk.Tk()
        Hovedside(ekg_root)
        ekg_root.mainloop()


# Hovedside class for main interface
class Hovedside:
    def __init__(self, root):
        self.root = root
        self.root.geometry('800x600')
        self.root.title("EKG Monitor")

        # Create frame for buttons and EKG graph
        self.frame = tk.Frame(root)
        self.frame.pack(fill=tk.BOTH, expand=True)

        # Create buttons
        self.create_patient_button = tk.Button(self.frame, text="Opret Patient", command=self.create_patient)
        self.create_patient_button.pack(pady=10)

        self.show_ekg_button = tk.Button(self.frame, text="Vis EKG Graf", command=self.show_ekg)
        self.show_ekg_button.pack(pady=10)

        self.patient_info = {}

    def create_patient(self):
        # Create a new window
        opret_patient_window = tk.Toplevel()
        opret_patient_window.title("Opret patient")
        opret_patient_window.geometry("400x200")

        global name_entry, age_entry, cpr_entry

        name_label = tk.Label(opret_patient_window, text="Fulde navn:")
        name_label.grid(row=0, column=0, padx=5, pady=5)
        name_entry = tk.Entry(opret_patient_window)
        name_entry.grid(row=0, column=1, padx=5, pady=5)

        age_label = tk.Label(opret_patient_window, text="Alder:")
        age_label.grid(row=1, column=0, padx=5, pady=5)
        age_entry = tk.Entry(opret_patient_window)
        age_entry.grid(row=1, column=1, padx=5, pady=5)

        cpr_label = tk.Label(opret_patient_window, text="Cpr nr.(xxxxxx-xxxx):")
        cpr_label.grid(row=2, column=0, padx=5, pady=5)

        # Validation command to ensure CPR is only 11 characters
        vcmd = (self.root.register(self.validate_cpr), '%P')
        cpr_entry = tk.Entry(opret_patient_window, validate='key', validatecommand=vcmd)
        cpr_entry.grid(row=2, column=1, padx=5, pady=5)

        def save_patient_info():
            name = name_entry.get()
            age = age_entry.get()
            cpr = cpr_entry.get()

            db_handler = DatabaseHandler()
            db_handler.insert_patient(name, age, cpr)
            db_handler.create_patient_ekg_data_table(cpr)

            self.patient_info = {'name': name, 'age': age, 'cpr': cpr}

            messagebox.showinfo("Success", "Patient info saved!")
            opret_patient_window.destroy()

        save_button = tk.Button(opret_patient_window, text="Save", command=save_patient_info)
        save_button.grid(row=4, column=1, padx=5, pady=5)

    def validate_cpr(self, new_value):
        return len(new_value) <= 11

    def show_ekg(self):
        if self.patient_info:
            ekg_app = EKG_graf(self.patient_info['name'], self.patient_info['age'], self.patient_info['cpr'])
            ekg_app.run()
        else:
            messagebox.showwarning("Warning", "No patient info available. Please create a patient first.")


if __name__ == "__main__":
    root = tk.Tk()
    app = LoginApp(root)
    root.mainloop()