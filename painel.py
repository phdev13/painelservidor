import os
import subprocess
import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QLabel, QStackedWidget, QPlainTextEdit, QPushButton, QLineEdit, QComboBox, 
    QScrollArea, QFrame, QMessageBox, QFileDialog, QHBoxLayout, QGridLayout)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QPixmap
import re
import traceback
import shutil

# Tema escuro moderno
THEME = {
    'bg': '#1E1E1E',
    'secondary_bg': '#252526',
    'accent': '#0078D4',
    'text': '#FFFFFF',
    'secondary_text': '#CCCCCC',
    'border': '#333333',
    'success': '#13A10E',
    'error': '#E74856',
    'warning': '#F9CE1D',
    'info': '#0078D4'
}

# Estilos QSS
STYLE = """
QMainWindow, QDialog {
    background-color: """ + THEME['bg'] + """;
}

QWidget {
    color: """ + THEME['text'] + """;
    font-family: 'Segoe UI', sans-serif;
}

QPushButton {
    background-color: """ + THEME['accent'] + """;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    color: white;
    font-weight: bold;
}

QPushButton:hover {
    background-color: """ + THEME['info'] + """;
}

QPushButton:pressed {
    background-color: #005A9E;
}

QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: """ + THEME['secondary_bg'] + """;
    border: 1px solid """ + THEME['border'] + """;
    border-radius: 4px;
    padding: 8px;
    color: """ + THEME['text'] + """;
}

QComboBox {
    background-color: """ + THEME['secondary_bg'] + """;
    border: 1px solid """ + THEME['border'] + """;
    border-radius: 4px;
    padding: 8px;
    color: """ + THEME['text'] + """;
}

QComboBox::drop-down {
    border: none;
}

QComboBox::down-arrow {
    image: url(:/icons/chevron-down.svg);
    width: 12px;
    height: 12px;
}

QScrollBar:vertical {
    background-color: """ + THEME['secondary_bg'] + """;
    width: 8px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: """ + THEME['accent'] + """;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
"""

# Variáveis globais
window = None
log_text = None
command_entry = None
server_running = False
server_process = None
config_btn = None
toggle_btn = None
status_label = None
server_jar_path = None

class ServerThread(QThread):
    output_received = Signal(str, str)  # Changed from pyqtSignal to Signal
    server_stopped = Signal(int)  # Changed from pyqtSignal to Signal

    def __init__(self, server_process):
        super().__init__()
        self.server_process = server_process
        self.running = True

    def run(self):
        try:
            while self.running and self.server_process:
                # Lê output
                if self.server_process.stdout:
                    line = self.server_process.stdout.readline()
                    if line:
                        line = line.strip()
                        # Detecta tipo de mensagem
                        msg_type = "info"
                        if "ERROR" in line or "SEVERE" in line:
                            msg_type = "error"
                        elif "WARN" in line:
                            msg_type = "warn"
                        self.output_received.emit(line, msg_type)

                # Verifica se processo terminou
                if self.server_process.poll() is not None:
                    self.server_stopped.emit(self.server_process.returncode)
                    break

        except Exception as e:
            self.output_received.emit(f"❌ Erro na thread: {str(e)}", "error")
        
    def stop(self):
        self.running = False

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Painel do Servidor Minecraft")
        self.resize(1200, 800)
        self.config_visible = False
        self.entries = {}
        self.script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.server_properties_path = os.path.join(self.script_dir, "server.properties")
        self.load_server_properties()
        self.setup_ui()
        self.server_thread = None
        # Detecta JAR automaticamente
        self.detect_server_jar()

    def detect_server_jar(self):
        global server_jar_path
        jars = [f for f in os.listdir(self.script_dir) if f.endswith('.jar')]
        if jars:
            server_jar_path = os.path.join(self.script_dir, jars[0])
            self.log_message(f"✅ Server JAR encontrado: {jars[0]}", "success")
        else:
            self.log_message("❌ Nenhum arquivo .jar encontrado!", "error")

    def load_server_properties(self):
        self.properties = {}
        if os.path.exists(self.server_properties_path):
            with open(self.server_properties_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip() and not line.startswith("#"):
                        if "=" in line:
                            key, value = line.strip().split("=", 1)
                            self.properties[key] = value

    def save_server_properties(self):
        with open(self.server_properties_path, "w", encoding="utf-8") as f:
            for key, value in self.properties.items():
                f.write(f"{key}={value}\n")

    def setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(10)

        # Logo no topo (sempre visível)
        self.logo_label = QLabel()
        self.logo_label.setFixedSize(400, 100)
        self.load_logo()
        self.main_layout.addWidget(self.logo_label, alignment=Qt.AlignCenter)

        # Stack Widget para alternar entre views
        self.stack = QStackedWidget()
        self.main_layout.addWidget(self.stack)

        # Página do Console
        self.console_page = QWidget()
        self.setup_console_page()
        self.stack.addWidget(self.console_page)

        # Página de Configurações
        self.config_page = QWidget()
        self.setup_config_page()
        self.stack.addWidget(self.config_page)

    def setup_console_page(self):
        layout = QVBoxLayout(self.console_page)

        # Barra superior com título e botões
        top_bar = QHBoxLayout()
        title = QLabel("Painel do Servidor")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        top_bar.addWidget(title)
        
        # Botões top-right
        buttons_layout = QHBoxLayout()
        
        save_log_btn = QPushButton("Salvar Log")
        save_log_btn.clicked.connect(self.save_log)
        save_log_btn.setStyleSheet("""
            QPushButton {
                padding: 5px 10px;
                background-color: """ + THEME['secondary_bg'] + """;
            }
        """)
        buttons_layout.addWidget(save_log_btn)
        
        clear_btn = QPushButton("Limpar Console")
        clear_btn.clicked.connect(self.clear_console)
        clear_btn.setStyleSheet("""
            QPushButton {
                padding: 5px 10px;
                background-color: """ + THEME['secondary_bg'] + """;
            }
        """)
        buttons_layout.addWidget(clear_btn)
        
        top_bar.addLayout(buttons_layout)
        self.status_label = QLabel("Status: Parado")
        self.status_label.setStyleSheet(f"color: {THEME['error']}; font-weight: bold;")
        top_bar.addWidget(self.status_label, alignment=Qt.AlignRight)
        layout.addLayout(top_bar)

        # Área de log
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumBlockCount(1000)
        layout.addWidget(self.log_text)

        # Botões de controle
        control_buttons = QHBoxLayout()
        
        self.toggle_btn = QPushButton("Iniciar Servidor")
        self.toggle_btn.clicked.connect(self.toggle_server)
        control_buttons.addWidget(self.toggle_btn)

        self.restart_btn = QPushButton("Reiniciar")
        self.restart_btn.clicked.connect(self.restart_server)
        self.restart_btn.setEnabled(False)
        control_buttons.addWidget(self.restart_btn)

        self.kill_btn = QPushButton("Forçar Parada")
        self.kill_btn.clicked.connect(self.kill_server)
        self.kill_btn.setEnabled(False)
        self.kill_btn.setStyleSheet(f"background-color: {THEME['error']};")
        control_buttons.addWidget(self.kill_btn)

        self.config_btn = QPushButton("Configurações")
        self.config_btn.clicked.connect(self.toggle_config_view)
        control_buttons.addWidget(self.config_btn)

        layout.addLayout(control_buttons)

        # Entrada de comando
        command_layout = QHBoxLayout()
        self.command_entry = QLineEdit()
        self.command_entry.setPlaceholderText("Digite um comando...")
        self.command_entry.returnPressed.connect(self.send_command)
        command_layout.addWidget(self.command_entry)

        send_btn = QPushButton("Enviar")
        send_btn.clicked.connect(self.send_command)
        command_layout.addWidget(send_btn)

        layout.addLayout(command_layout)

    def clear_console(self):
        if self.log_text:
            self.log_text.clear()
            self.log_message("Console limpo!", "info")

    def setup_config_page(self):
        layout = QVBoxLayout(self.config_page)
        
        # Header com botões alinhados
        header = QHBoxLayout()
        title = QLabel("Configurações do Servidor")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        header.addWidget(title)
        
        # Botões agrupados à direita
        buttons = QHBoxLayout()
        save_btn = QPushButton("Salvar")
        save_btn.clicked.connect(self.save_config)
        save_btn.setStyleSheet(f"background-color: {THEME['success']};")
        
        reset_btn = QPushButton("Resetar")
        reset_btn.clicked.connect(self.reset_config)
        reset_btn.setStyleSheet(f"background-color: {THEME['warning']};")
        
        back_btn = QPushButton("Voltar")
        back_btn.clicked.connect(self.toggle_config_view)
        
        buttons.addWidget(save_btn)
        buttons.addWidget(reset_btn)
        buttons.addWidget(back_btn)
        header.addLayout(buttons)
        layout.addLayout(header)

        # Configurações em Cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # Cards de configuração
        self.add_config_card(scroll_layout, "Personalização", [
            ("Logo do Servidor", "server-logo", "logo")  # Novo tipo de campo
        ])

        self.add_config_card(scroll_layout, "Configurações Básicas", [
            ("IP do Servidor", "server-ip", "text"),
            ("Nome do Servidor", "server-name", "text"),
            ("MOTD", "motd", "text"),
            ("Porta", "server-port", "text"),
            ("Máx. Jogadores", "max-players", "text"),
            ("Online Mode", "online-mode", "combo", ["true", "false"])
        ])

        self.add_config_card(scroll_layout, "Gameplay", [
            ("Modo de Jogo", "gamemode", "combo", ["0", "1", "2", "3"]),
            ("PVP", "pvp", "combo", ["true", "false"]),
            ("Dificuldade", "difficulty", "combo", ["0", "1", "2", "3"]),
            ("Hardcore", "hardcore", "combo", ["false", "true"]),
            ("View Distance", "view-distance", "text"),
            ("Spawn Protection", "spawn-protection", "text")
        ])

        self.add_config_card(scroll_layout, "Recursos", [
            ("Command Blocks", "enable-command-block", "combo", ["false", "true"]),
            ("Whitelist", "white-list", "combo", ["false", "true"]),
            ("Resource Pack", "resource-pack", "text"),
            ("Force Gamemode", "force-gamemode", "combo", ["false", "true"]),
            ("Allow Flight", "allow-flight", "combo", ["false", "true"]),
            ("Allow Nether", "allow-nether", "combo", ["true", "false"])
        ])

        self.add_config_card(scroll_layout, "Performance", [
            ("Max Build Height", "max-build-height", "text"),
            ("Max Tick Time", "max-tick-time", "text"),
            ("Entity Broadcast Range", "entity-broadcast-range-percentage", "text"),
            ("Simulation Distance", "simulation-distance", "text"),
            ("Network Compression", "network-compression-threshold", "text")
        ])

        self.add_config_card(scroll_layout, "Avançado", [
            ("Query", "enable-query", "combo", ["false", "true"]),
            ("Query Port", "query.port", "text"),
            ("RCON", "enable-rcon", "combo", ["false", "true"]),
            ("RCON Port", "rcon.port", "text"),
            ("RCON Password", "rcon.password", "text"),
            ("Level Type", "level-type", "combo", ["DEFAULT", "FLAT", "LARGEBIOMES", "AMPLIFIED"]),
            ("Generator Settings", "generator-settings", "text"),
            ("Level Seed", "level-seed", "text")
        ])

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

    def add_config_card(self, parent_layout, title, fields):
        card = ConfigCard(title)
        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(10)
        
        for row, (label, key, type_field, *args) in enumerate(fields):
            label_widget = QLabel(label)
            label_widget.setFixedWidth(200)
            grid.addWidget(label_widget, row, 0)
            
            if type_field == "logo":
                # Campo especial para logo
                preview = QLabel()
                preview.setFixedSize(200, 100)  # Tamanho fixo para preview
                preview.setStyleSheet("""
                    background: """ + THEME['secondary_bg'] + """;
                    border: 1px solid """ + THEME['border'] + """;
                    border-radius: 4px;
                """)
                if hasattr(self, 'logo_path') and os.path.exists(self.logo_path):
                    pixmap = QPixmap(self.logo_path)
                    scaled_pixmap = pixmap.scaled(200, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    # Centraliza a imagem no preview
                    preview.setAlignment(Qt.AlignCenter)
                    preview.setPixmap(scaled_pixmap)
                
                select_btn = QPushButton("Escolher Logo")
                select_btn.setFixedWidth(150)  # Largura fixa para o botão
                select_btn.clicked.connect(lambda: self.select_logo(preview))
                
                field_layout = QHBoxLayout()
                field_layout.addWidget(preview)
                field_layout.addSpacing(20)  # Adiciona 20px de espaço entre o preview e o botão
                field_layout.addWidget(select_btn)
                field_layout.addStretch()  # Adiciona espaço flexível no final
                grid.addLayout(field_layout, row, 1)
                self.entries[key] = preview
            elif type_field == "combo":
                field = QComboBox()
                field.addItems(args[0])
                if key in self.properties:
                    field.setCurrentText(self.properties[key])
                self.entries[key] = field
                grid.addWidget(field, row, 1)
            else:
                field = QLineEdit()
                if key in self.properties:
                    field.setText(self.properties[key])
                self.entries[key] = field
                grid.addWidget(field, row, 1)
        
        card.layout.addLayout(grid)
        parent_layout.addWidget(card)

    def select_logo(self, preview_label):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Logo",
            "",
            "Imagens (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_path:
            try:
                # Salva na pasta do servidor
                dest_path = os.path.join(self.script_dir, "redenoxtitle.png")
                shutil.copy2(file_path, dest_path)
                
                # Atualiza preview
                pixmap = QPixmap(dest_path)
                preview_label.setPixmap(pixmap.scaledToHeight(100, Qt.SmoothTransformation))
                self.logo_path = dest_path
                
                # Atualiza logo principal
                self.load_logo()
                self.log_message("✅ Logo atualizada com sucesso!", "success")
            except Exception as e:
                self.log_message(f"❌ Erro ao atualizar logo: {str(e)}", "error")

    def toggle_config_view(self):
        current_index = self.stack.currentIndex()
        new_index = 1 if current_index == 0 else 0
        self.stack.setCurrentIndex(new_index)

    def load_logo(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(script_dir, "redenoxtitle.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            scaled = pixmap.scaled(400, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo_label.setPixmap(scaled)

    def save_config(self):
        for key, widget in self.entries.items():
            if isinstance(widget, QComboBox):
                self.properties[key] = widget.currentText()
            elif isinstance(widget, QLabel) and key == "server-logo":
                # Ignora o campo de logo
                continue
            else:
                self.properties[key] = widget.text()
        self.save_server_properties()
        
        # Feedback visual através de MessageBox
        msg = QMessageBox(self)
        msg.setWindowTitle("Sucesso")
        msg.setText("✅ Configurações salvas com sucesso!")
        msg.setIcon(QMessageBox.Information)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: """ + THEME['bg'] + """;
            }
            QPushButton {
                width: 100px;
            }
        """)
        msg.exec()

    def reset_config(self):
        # Confirmação antes de resetar
        confirm = QMessageBox(self)
        confirm.setWindowTitle("Confirmar Reset")
        confirm.setText("⚠️ Tem certeza que deseja resetar todas as configurações?")
        confirm.setInformativeText("Isso irá restaurar os valores originais do arquivo server.properties.")
        confirm.setIcon(QMessageBox.Warning)
        confirm.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        confirm.setDefaultButton(QMessageBox.No)
        confirm.setStyleSheet("""
            QMessageBox {
                background-color: """ + THEME['bg'] + """;
            }
            QPushButton {
                width: 100px;
            }
        """)
        
        if confirm.exec() == QMessageBox.Yes:
            self.load_server_properties()
            # Atualiza os campos na interface
            for key, widget in self.entries.items():
                if key in self.properties:
                    if isinstance(widget, QComboBox):
                        widget.setCurrentText(self.properties[key])
                    elif isinstance(widget, QLabel) and key == "server-logo":
                        continue
                    else:
                        widget.setText(self.properties[key])
                else:
                    if isinstance(widget, QComboBox):
                        widget.setCurrentIndex(0)
                    elif isinstance(widget, QLabel) and key == "server-logo":
                        continue
                    else:
                        widget.setText("")
            
            # Feedback visual de sucesso
            msg = QMessageBox(self)
            msg.setWindowTitle("Sucesso")
            msg.setText("✅ Configurações resetadas com sucesso!")
            msg.setIcon(QMessageBox.Information)
            msg.setStandardButtons(QMessageBox.Ok)
            msg.setStyleSheet("""
                QMessageBox {
                    background-color: """ + THEME['bg'] + """;
                }
                QPushButton {
                    width: 100px;
                }
            """)
            msg.exec()

    def toggle_server(self):
        global server_running, server_process, server_jar_path
        if server_running:
            self.stop_server()
        else:
            self.start_server()

    def start_server(self):
        global server_running, server_process, server_jar_path
        try:
            if not server_jar_path or not os.path.exists(server_jar_path):
                raise FileNotFoundError("❌ Arquivo server.jar não encontrado!")

            # Tenta iniciar o servidor
            command = f"java -Xmx1G -Xms1G -Dfile.encoding=UTF8 -jar \"{server_jar_path}\" nogui"
            self.log_message(f"Executando comando: {command}", "info")
            
            process = subprocess.Popen(
                command,
                shell=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.script_dir,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            # Verifica se o processo iniciou
            if not process or process.poll() is not None:
                raise RuntimeError("❌ Falha ao iniciar o processo do servidor")
            
            server_process = process
            # Usa QThread ao invés de threading
            self.server_thread = ServerThread(process)
            self.server_thread.output_received.connect(self.log_message)
            self.server_thread.server_stopped.connect(self.handle_server_stopped)
            self.server_thread.start()
            
            self.log_message("🟢 Servidor iniciado com sucesso!", "success")
            self.toggle_btn.setText("Parar Servidor")
            self.status_label.setText("Status: Rodando")
            self.status_label.setStyleSheet(f"color: {THEME['success']}; font-weight: bold;")
            self.restart_btn.setEnabled(True)
            self.kill_btn.setEnabled(True)
            self.config_btn.setEnabled(False)
            server_running = True

        except FileNotFoundError as e:
            self.log_message(str(e), "error")
            self.log_message("⚠️ Verifique se o arquivo .jar está na pasta do script", "warn")
        except Exception as e:
            self.log_message(f"❌ Erro crítico: {str(e)}", "error")
            self.log_message("⚠️ Stack trace completo:", "warn")
            import traceback
            self.log_message(traceback.format_exc(), "error")
        finally:
            if not server_running:
                self.reset_server_state()

    def handle_server_stopped(self, exit_code):
        if exit_code != 0:
            self.log_message(f"⚠️ Servidor finalizado com código: {exit_code}", "warn")
        self.reset_server_state()

    def stop_server(self):
        global server_running, server_process
        if self.server_thread:
            self.server_thread.stop()
        if server_process:
            try:
                self.send_command("stop")
                server_process.wait(timeout=10)
            except:
                self.kill_server()
        self.reset_server_state()
        self.log_message("🔴 Servidor parado.")

    def kill_server(self):
        global server_running, server_process
        if server_process:
            server_process.kill()
            server_process = None
        self.reset_server_state()
        self.log_message("🔴 Servidor finalizado (kill).")

    def restart_server(self):
        self.stop_server()
        QTimer.singleShot(2000, self.start_server)  # Espera 2 segundos e reinicia

    def reset_server_state(self):
        global server_running, server_process
        server_process = None
        server_running = False
        self.toggle_btn.setText("Iniciar Servidor")
        self.status_label.setText("Status: Parado")
        self.status_label.setStyleSheet(f"color: {THEME['error']}; font-weight: bold;")
        self.restart_btn.setEnabled(False)
        self.kill_btn.setEnabled(False)
        self.config_btn.setEnabled(True)  # Reabilita config quando para

    def log_message(self, message, type="info"):
        if not message:
            return
        
        try:
            # Remove timestamp se presente
            message = re.sub(r'\[\d{2}:\d{2}:\d{2}\]\s*', '', message)
            
            colors = {
                "info": "#FFFFFF",     # Branco
                "warn": "#F9CE1D",     # Amarelo
                "error": "#E74856",    # Vermelho
                "success": "#13A10E",  # Verde
                "plugin": "#0078D4",   # Azul
                "cmd": "#BB86FC"       # Roxo
            }

            # Detecta padrões específicos e aplica cores
            if "[" in message and "]" in message:
                # Colore nomes de plugins
                message = re.sub(r'\[(.*?)\]', 
                    lambda m: f'<font color="{colors["plugin"]}">[{m.group(1)}]</font>', 
                    message)
            
            # Colore palavras-chave
            keywords = {
                "INFO": "success",
                "WARN": "warn", 
                "WARNING": "warn",
                "ERROR": "error",
                "SEVERE": "error",
                "Loading": "info",
                "Done": "success",
                "Starting": "info",
                "Stopping": "warn"
            }

            for keyword, color_type in keywords.items():
                if keyword in message:
                    message = message.replace(keyword, 
                        f'<font color="{colors[color_type]}">{keyword}</font>')

            # Aplica cor base da mensagem
            message = f'<span style="color: {colors.get(type, colors["info"])}">{message}</span>'
            self.log_text.appendHtml(message)

        except Exception as e:
            print(f"Erro ao formatar mensagem: {e}")

    def send_command(self):
        global server_process
        command = self.command_entry.text().strip()
        if server_running and server_process and server_process.stdin:
            try:
                server_process.stdin.write(command + "\n")
                server_process.stdin.flush()
                self.log_message(f"> {command}")
            except Exception as e:
                self.log_message(f"❌ Erro ao enviar comando: {e}", "error")
        else:
            self.log_message("⚠️ Servidor não está ativo.", "warn")
        self.command_entry.clear()

    def save_log(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Salvar Log", "", "Arquivos de texto (*.txt);;Todos os arquivos (*.*)")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.toPlainText())
                self.log_message("✅ Log salvo com sucesso!", "success")
            except Exception as e:
                self.log_message(f"❌ Erro ao salvar log: {e}", "error")

    def get_icon_button_style(self):
        return """
            QPushButton {
                background-color: transparent;
                border: 1px solid """ + THEME['border'] + """;
                font-size: 14px;
                margin: 0 2px;
            }
            QPushButton:hover {
                background-color: """ + THEME['secondary_bg'] + """;
                border: 1px solid """ + THEME['accent'] + """;
            }
        """

class ConfigCard(QFrame):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("configCard")
        self.setStyleSheet("""
            #configCard {
                background-color: """ + THEME['secondary_bg'] + """;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(12)
        
        # Título do card
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: """ + THEME['accent'] + """;
        """)
        self.layout.addWidget(title_label)

if __name__ == "__main__":
    try:
        # Tratamento de erro global
        def exception_hook(exctype, value, tb):
            print('Exception hook triggered')
            traceback.print_exception(exctype, value, tb)
            sys.__excepthook__(exctype, value, tb)
        
        sys.excepthook = exception_hook

        # Verifica se já existe uma instância rodando
        for proc in QApplication.instance() or []:
            proc.quit()
        
        # Cria nova instância
        app = QApplication.instance()
        if not app:
            app = QApplication(sys.argv)
        
        app.setStyleSheet(STYLE)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"Erro crítico na inicialização: {e}")
        traceback.print_exc()
        input("Pressione Enter para sair...")