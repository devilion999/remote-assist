using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.IO;
using Newtonsoft.Json;
using System.Net.Http;

namespace RemoteAccessClient
{
    public class RemoteAccessClient : Form
    {
        private const string SERVER_URL = "http://your-server-address:8000";
        
        private TextBox sessionCodeTextBox;
        private Button connectButton;
        private Label statusLabel;
        private PictureBox screenDisplay;
        
        private UdpClient udpClient;
        private IPEndPoint serverEndpoint;
        private bool isConnected = false;
        private bool isStreaming = false;
        
        private Thread captureThread;
        private Thread receiveThread;
        
        private int serverPort = 0;
        private string sessionCode = "";

        public RemoteAccessClient()
        {
            InitializeUI();
        }

        private void InitializeUI()
        {
            this.Text = "Remote Access Client";
            this.Size = new Size(800, 600);
            this.StartPosition = FormStartPosition.CenterScreen;
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;

            // Connection Panel
            Panel connectionPanel = new Panel
            {
                Dock = DockStyle.Top,
                Height = 100,
                Padding = new Padding(10),
                BackColor = Color.FromArgb(240, 240, 240)
            };

            Label instructionLabel = new Label
            {
                Text = "Enter Session Code:",
                Location = new Point(10, 15),
                AutoSize = true,
                Font = new Font("Segoe UI", 10, FontStyle.Bold)
            };

            sessionCodeTextBox = new TextBox
            {
                Location = new Point(10, 40),
                Size = new Size(200, 30),
                Font = new Font("Courier New", 14, FontStyle.Bold),
                MaxLength = 9,
                TextAlign = HorizontalAlignment.Center
            };

            connectButton = new Button
            {
                Text = "Connect",
                Location = new Point(220, 40),
                Size = new Size(100, 30),
                BackColor = Color.FromArgb(37, 99, 235),
                ForeColor = Color.White,
                FlatStyle = FlatStyle.Flat,
                Font = new Font("Segoe UI", 10, FontStyle.Bold)
            };
            connectButton.FlatAppearance.BorderSize = 0;
            connectButton.Click += ConnectButton_Click;

            statusLabel = new Label
            {
                Text = "Status: Disconnected",
                Location = new Point(330, 45),
                AutoSize = true,
                Font = new Font("Segoe UI", 9),
                ForeColor = Color.Gray
            };

            connectionPanel.Controls.Add(instructionLabel);
            connectionPanel.Controls.Add(sessionCodeTextBox);
            connectionPanel.Controls.Add(connectButton);
            connectionPanel.Controls.Add(statusLabel);

            // Screen Display
            screenDisplay = new PictureBox
            {
                Dock = DockStyle.Fill,
                SizeMode = PictureBoxSizeMode.Zoom,
                BackColor = Color.Black
            };

            this.Controls.Add(screenDisplay);
            this.Controls.Add(connectionPanel);

            // Event handlers
            this.FormClosing += RemoteAccessClient_FormClosing;
            sessionCodeTextBox.KeyPress += SessionCodeTextBox_KeyPress;
        }

        private void SessionCodeTextBox_KeyPress(object sender, KeyPressEventArgs e)
        {
            // Only allow numbers
            if (!char.IsDigit(e.KeyChar) && e.KeyChar != (char)Keys.Back)
            {
                e.Handled = true;
            }

            // Auto-connect on 9 digits
            if (sessionCodeTextBox.Text.Length == 8 && char.IsDigit(e.KeyChar))
            {
                BeginInvoke(new Action(() => ConnectButton_Click(null, null)));
            }
        }

        private async void ConnectButton_Click(object sender, EventArgs e)
        {
            if (isConnected)
            {
                Disconnect();
                return;
            }

            sessionCode = sessionCodeTextBox.Text.Trim();
            
            if (sessionCode.Length != 9)
            {
                MessageBox.Show("Please enter a valid 9-digit session code.", "Invalid Code", 
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            UpdateStatus("Connecting...", Color.Orange);
            connectButton.Enabled = false;

            try
            {
                // Get session info from server
                using (HttpClient client = new HttpClient())
                {
                    var response = await client.GetAsync($"{SERVER_URL}/api/sessions/{sessionCode}/info");
                    
                    if (!response.IsSuccessStatusCode)
                    {
                        throw new Exception("Session not found or has expired");
                    }

                    var json = await response.Content.ReadAsStringAsync();
                    var sessionInfo = JsonConvert.DeserializeObject<SessionInfo>(json);
                    
                    serverPort = sessionInfo.udp_port;
                }

                // Initialize UDP connection
                udpClient = new UdpClient();
                serverEndpoint = new IPEndPoint(IPAddress.Parse(GetServerIP()), serverPort);
                
                // Send initial handshake
                SendHandshake();

                // Start receiving data
                receiveThread = new Thread(ReceiveData);
                receiveThread.IsBackground = true;
                receiveThread.Start();

                // Start screen capture
                captureThread = new Thread(CaptureScreen);
                captureThread.IsBackground = true;
                captureThread.Start();

                isConnected = true;
                UpdateStatus("Connected", Color.Green);
                connectButton.Text = "Disconnect";
                sessionCodeTextBox.Enabled = false;
            }
            catch (Exception ex)
            {
                UpdateStatus("Connection Failed", Color.Red);
                MessageBox.Show($"Connection failed: {ex.Message}", "Error", 
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            finally
            {
                connectButton.Enabled = true;
            }
        }

        private void SendHandshake()
        {
            var handshake = new
            {
                type = "handshake",
                session_code = sessionCode,
                screen_width = Screen.PrimaryScreen.Bounds.Width,
                screen_height = Screen.PrimaryScreen.Bounds.Height,
                timestamp = DateTime.UtcNow.Ticks
            };

            string json = JsonConvert.SerializeObject(handshake);
            byte[] data = Encoding.UTF8.GetBytes(json);
            udpClient.Send(data, data.Length, serverEndpoint);
        }

        private void CaptureScreen()
        {
            const int FRAME_RATE = 15; // FPS
            const int FRAME_DELAY = 1000 / FRAME_RATE;
            const int QUALITY = 60; // JPEG quality (1-100)
            const int MAX_PACKET_SIZE = 60000; // ~60KB per packet

            while (isConnected)
            {
                try
                {
                    // Capture screen
                    Rectangle bounds = Screen.PrimaryScreen.Bounds;
                    using (Bitmap screenshot = new Bitmap(bounds.Width, bounds.Height))
                    {
                        using (Graphics g = Graphics.FromImage(screenshot))
                        {
                            g.CopyFromScreen(Point.Empty, Point.Empty, bounds.Size);
                        }

                        // Compress to JPEG
                        using (MemoryStream ms = new MemoryStream())
                        {
                            EncoderParameters encoderParams = new EncoderParameters(1);
                            encoderParams.Param[0] = new EncoderParameter(
                                System.Drawing.Imaging.Encoder.Quality, (long)QUALITY);
                            
                            ImageCodecInfo jpegCodec = GetEncoderInfo("image/jpeg");
                            screenshot.Save(ms, jpegCodec, encoderParams);
                            
                            byte[] imageData = ms.ToArray();

                            // Send frame data via UDP
                            SendFrameData(imageData);
                        }
                    }

                    Thread.Sleep(FRAME_DELAY);
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"Capture error: {ex.Message}");
                }
            }
        }

        private void SendFrameData(byte[] imageData)
        {
            const int CHUNK_SIZE = 60000;
            int totalChunks = (int)Math.Ceiling((double)imageData.Length / CHUNK_SIZE);
            long frameId = DateTime.UtcNow.Ticks;

            for (int i = 0; i < totalChunks; i++)
            {
                int offset = i * CHUNK_SIZE;
                int length = Math.Min(CHUNK_SIZE, imageData.Length - offset);
                
                // Create packet header
                using (MemoryStream ms = new MemoryStream())
                using (BinaryWriter writer = new BinaryWriter(ms))
                {
                    writer.Write((byte)1); // Packet type: Frame data
                    writer.Write(frameId);
                    writer.Write(i);
                    writer.Write(totalChunks);
                    writer.Write(imageData.Length);
                    writer.Write(imageData, offset, length);

                    byte[] packet = ms.ToArray();
                    udpClient.Send(packet, packet.Length, serverEndpoint);
                }
            }
        }

        private void ReceiveData()
        {
            IPEndPoint remoteEndpoint = new IPEndPoint(IPAddress.Any, 0);

            while (isConnected)
            {
                try
                {
                    byte[] data = udpClient.Receive(ref remoteEndpoint);
                    
                    if (data.Length > 0)
                    {
                        ProcessReceivedData(data);
                    }
                }
                catch (Exception ex)
                {
                    if (isConnected)
                    {
                        Console.WriteLine($"Receive error: {ex.Message}");
                    }
                }
            }
        }

        private void ProcessReceivedData(byte[] data)
        {
            using (MemoryStream ms = new MemoryStream(data))
            using (BinaryReader reader = new BinaryReader(ms))
            {
                byte packetType = reader.ReadByte();

                switch (packetType)
                {
                    case 2: // Mouse event
                        int x = reader.ReadInt32();
                        int y = reader.ReadInt32();
                        byte button = reader.ReadByte();
                        bool down = reader.ReadBoolean();
                        SimulateMouseEvent(x, y, button, down);
                        break;

                    case 3: // Keyboard event
                        ushort key = reader.ReadUInt16();
                        bool keyDown = reader.ReadBoolean();
                        SimulateKeyboardEvent(key, keyDown);
                        break;

                    case 4: // Control message
                        string message = Encoding.UTF8.GetString(reader.ReadBytes((int)(ms.Length - ms.Position)));
                        HandleControlMessage(message);
                        break;
                }
            }
        }

        [DllImport("user32.dll")]
        private static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, int dwExtraInfo);

        [DllImport("user32.dll")]
        private static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, int dwExtraInfo);

        private void SimulateMouseEvent(int x, int y, byte button, bool down)
        {
            const uint MOUSEEVENTF_MOVE = 0x0001;
            const uint MOUSEEVENTF_LEFTDOWN = 0x0002;
            const uint MOUSEEVENTF_LEFTUP = 0x0004;
            const uint MOUSEEVENTF_RIGHTDOWN = 0x0008;
            const uint MOUSEEVENTF_RIGHTUP = 0x0010;
            const uint MOUSEEVENTF_ABSOLUTE = 0x8000;

            // Calculate absolute position
            int screenWidth = Screen.PrimaryScreen.Bounds.Width;
            int screenHeight = Screen.PrimaryScreen.Bounds.Height;
            uint absoluteX = (uint)(x * 65535 / screenWidth);
            uint absoluteY = (uint)(y * 65535 / screenHeight);

            // Move mouse
            mouse_event(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, absoluteX, absoluteY, 0, 0);

            // Handle button
            if (button == 1) // Left button
            {
                mouse_event(down ? MOUSEEVENTF_LEFTDOWN : MOUSEEVENTF_LEFTUP, 0, 0, 0, 0);
            }
            else if (button == 2) // Right button
            {
                mouse_event(down ? MOUSEEVENTF_RIGHTDOWN : MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0);
            }
        }

        private void SimulateKeyboardEvent(ushort key, bool down)
        {
            const uint KEYEVENTF_KEYUP = 0x0002;
            keybd_event((byte)key, 0, down ? 0 : KEYEVENTF_KEYUP, 0);
        }

        private void HandleControlMessage(string message)
        {
            var msg = JsonConvert.DeserializeObject<dynamic>(message);
            string type = msg.type;

            if (type == "disconnect")
            {
                BeginInvoke(new Action(() => Disconnect()));
            }
        }

        private void Disconnect()
        {
            isConnected = false;

            if (captureThread != null && captureThread.IsAlive)
            {
                captureThread.Join(1000);
            }

            if (receiveThread != null && receiveThread.IsAlive)
            {
                receiveThread.Join(1000);
            }

            if (udpClient != null)
            {
                udpClient.Close();
                udpClient = null;
            }

            UpdateStatus("Disconnected", Color.Gray);
            connectButton.Text = "Connect";
            sessionCodeTextBox.Enabled = true;
            sessionCodeTextBox.Text = "";
        }

        private void UpdateStatus(string status, Color color)
        {
            if (statusLabel.InvokeRequired)
            {
                statusLabel.BeginInvoke(new Action(() => UpdateStatus(status, color)));
                return;
            }

            statusLabel.Text = $"Status: {status}";
            statusLabel.ForeColor = color;
        }

        private string GetServerIP()
        {
            // Extract IP from SERVER_URL
            Uri uri = new Uri(SERVER_URL);
            return uri.Host;
        }

        private ImageCodecInfo GetEncoderInfo(string mimeType)
        {
            ImageCodecInfo[] codecs = ImageCodecInfo.GetImageEncoders();
            foreach (ImageCodecInfo codec in codecs)
            {
                if (codec.MimeType == mimeType)
                    return codec;
            }
            return null;
        }

        private void RemoteAccessClient_FormClosing(object sender, FormClosingEventArgs e)
        {
            if (isConnected)
            {
                Disconnect();
            }
        }

        [STAThread]
        static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new RemoteAccessClient());
        }
    }

    public class SessionInfo
    {
        public string session_code { get; set; }
        public int udp_port { get; set; }
        public string status { get; set; }
    }
}
