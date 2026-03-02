using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows.Forms;
using System.Drawing;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new MainForm());
    }
}

internal sealed class MainForm : Form
{
    private const string StudyIdExample = "es: PNRR oppure PNRR 19";
    private const string CategoriesExample = "es: animali frutta verdura";

    private readonly TextBox _txtRaw = new TextBox();
    private readonly TextBox _txtPatients = new TextBox();
    private readonly TextBox _txtStudyId = new TextBox();

    private readonly TextBox _txtOutput = new TextBox();
    private readonly TextBox _txtSchemeDir = new TextBox();
    private readonly TextBox _txtResultsDir = new TextBox();
    private readonly TextBox _txtIdPrefix = new TextBox();
    private readonly TextBox _txtIdSuffix = new TextBox();
    private readonly TextBox _txtCategories = new TextBox();
    private readonly TextBox _txtCnAlpha = new TextBox();
    private readonly TextBox _txtCnWindow = new TextBox();
    private readonly TextBox _txtCnThreshold = new TextBox();

    private readonly NumericUpDown _numMinOtRun = new NumericUpDown();
    private readonly CheckBox _chkInvert = new CheckBox();
    private readonly CheckBox _chkNoGenderSplits = new CheckBox();

    private readonly Button _btnRun = new Button();
    private readonly TextBox _txtLog = new TextBox();
    private readonly Label _lblStatus = new Label();
    private readonly ToolTip _toolTip = new ToolTip();
    private SplitContainer _split;
    private FlowLayoutPanel _flow;
    private TableLayoutPanel _essentialTable;
    private GroupBox _advancedGroup;
    private TableLayoutPanel _advancedTable;
    private FlowLayoutPanel _runLine;

    public MainForm()
    {
        Text = "SNAFU - Launcher";
        Width = 980;
        Height = 760;
        StartPosition = FormStartPosition.CenterScreen;
        try
        {
            Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
        }
        catch
        {
            // fallback: keep default icon
        }

        string baseDir = AppBaseDir();
        _txtRaw.Text = Path.Combine(baseDir, "fluency_data", "snafu_downloaded.csv");
        _txtPatients.Text = Path.Combine(baseDir, "fluency_data", "patients.csv");
        _txtStudyId.Text = "";
        _txtOutput.Text = Path.Combine(baseDir, "fluency_data", "snafu.csv");
        _txtSchemeDir.Text = Path.Combine(baseDir, "schemes");
        _txtResultsDir.Text = Path.Combine(baseDir, "results");
        _txtCnAlpha.Text = "0.05";
        _txtCnWindow.Text = "2";
        _txtCnThreshold.Text = "2";
        _numMinOtRun.Value = 3;
        _numMinOtRun.Minimum = 1;
        _numMinOtRun.Maximum = 50;
        _toolTip.AutoPopDelay = 12000;
        _toolTip.InitialDelay = 200;
        _toolTip.ReshowDelay = 100;
        _toolTip.ShowAlways = true;

        BuildUi();
    }

    private void BuildUi()
    {
        _split = new SplitContainer();
        _split.Dock = DockStyle.Fill;
        _split.Orientation = Orientation.Horizontal;
        _split.Panel1MinSize = 320;
        _split.Panel2MinSize = 120;
        _split.FixedPanel = FixedPanel.Panel2;
        Controls.Add(_split);

        Panel topPanel = new Panel();
        topPanel.Dock = DockStyle.Fill;
        topPanel.AutoScroll = false;
        _split.Panel1.Controls.Add(topPanel);

        _flow = new FlowLayoutPanel();
        _flow.Dock = DockStyle.Fill;
        _flow.AutoScroll = true;
        _flow.AutoSize = false;
        _flow.FlowDirection = FlowDirection.TopDown;
        _flow.WrapContents = false;
        _flow.Padding = new Padding(12);
        topPanel.Controls.Add(_flow);

        _essentialTable = BuildEssentialTable();
        _flow.Controls.Add(_essentialTable);

        _advancedGroup = BuildAdvancedTable();
        _flow.Controls.Add(_advancedGroup);

        _runLine = new FlowLayoutPanel();
        _runLine.AutoSize = true;
        _runLine.FlowDirection = FlowDirection.LeftToRight;
        _runLine.WrapContents = false;
        _runLine.Margin = new Padding(3, 12, 3, 3);

        _btnRun.Text = "Esegui";
        _btnRun.Width = 120;
        _btnRun.Height = 32;
        _btnRun.Click += RunClicked;
        _runLine.Controls.Add(_btnRun);

        _lblStatus.Text = "Pronto";
        _lblStatus.AutoSize = true;
        _lblStatus.Padding = new Padding(12, 8, 0, 0);
        _runLine.Controls.Add(_lblStatus);

        _flow.Controls.Add(_runLine);

        _txtLog.Dock = DockStyle.Fill;
        _txtLog.Multiline = true;
        _txtLog.ScrollBars = ScrollBars.Both;
        _txtLog.ReadOnly = true;
        _txtLog.WordWrap = false;
        _split.Panel2.Controls.Add(_txtLog);

        _flow.SizeChanged += delegate { UpdateResponsiveLayout(); };
        topPanel.SizeChanged += delegate { UpdateResponsiveLayout(); };
        _split.SizeChanged += delegate { UpdateSplitLayout(); };
        Shown += delegate
        {
            UpdateSplitLayout();
            UpdateResponsiveLayout();
        };
    }

    private TableLayoutPanel BuildEssentialTable()
    {
        TableLayoutPanel t = NewTable();
        AddFileRow(
            t,
            "Raw CSV (obbligatorio)",
            _txtRaw,
            false,
            "File CSV di input principale. Campo obbligatorio."
        );
        AddFileRow(
            t,
            "Patients CSV (opzionale)",
            _txtPatients,
            false,
            "CSV pazienti usato insieme a Study ID per filtrare i soggetti."
        );
        AddPlainRow(
            t,
            "Study ID (opzionale)",
            _txtStudyId,
            StudyIdExample,
            "Uno o piu codici studio separati da spazio, virgola o punto e virgola."
        );
        return t;
    }

    private GroupBox BuildAdvancedTable()
    {
        GroupBox box = new GroupBox();
        box.Text = "Parametri";
        box.AutoSize = false;
        box.Padding = new Padding(10);
        box.Margin = new Padding(3, 0, 3, 3);

        _advancedTable = NewTable();
        AddFileRow(_advancedTable, "Output CSV", _txtOutput, true, "File CSV standardizzato prodotto da keep_columns.");
        AddFolderRow(_advancedTable, "Cartella Schemi", _txtSchemeDir, "Cartella con file schema per categoria (es: animali.csv).");
        AddFolderRow(_advancedTable, "Cartella Risultati", _txtResultsDir, "Cartella dove salvare CSV risultati, reti e grafici.");
        AddPlainRow(_advancedTable, "ID Prefix", _txtIdPrefix, "", "Considera solo id che iniziano con questo prefisso.");
        AddPlainRow(_advancedTable, "ID Suffix", _txtIdSuffix, "", "Considera solo id che finiscono con questo suffisso.");
        AddPlainRow(_advancedTable, "Categorie", _txtCategories, CategoriesExample, "Elenco categorie da analizzare. Lascia vuoto per auto-rilevamento.");
        AddNumericRow(_advancedTable, "Min OT Run", _numMinOtRun, "Rimuove sequenze consecutive out-of-topic con lunghezza >= valore.");
        AddPlainRow(_advancedTable, "CN Alpha", _txtCnAlpha, "0.05", "Parametro alpha del metodo Conceptual Network.");
        AddPlainRow(_advancedTable, "CN Window", _txtCnWindow, "2", "Finestra temporale del metodo Conceptual Network.");
        AddPlainRow(_advancedTable, "CN Threshold", _txtCnThreshold, "2", "Soglia minima per tenere un arco nel Conceptual Network.");

        FlowLayoutPanel flags = new FlowLayoutPanel();
        flags.AutoSize = true;
        flags.FlowDirection = FlowDirection.LeftToRight;
        flags.WrapContents = false;
        _chkInvert.Text = "Invert";
        _chkInvert.AutoSize = true;
        _chkNoGenderSplits.Text = "No gender splits";
        _chkNoGenderSplits.AutoSize = true;
        flags.Controls.Add(_chkInvert);
        flags.Controls.Add(_chkNoGenderSplits);

        int row = _advancedTable.RowCount++;
        _advancedTable.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        _advancedTable.Controls.Add(CreateLabelWithHelp("Flag", "Invert: inverte il filtro Study ID. No gender splits: non crea output separati M/F."), 0, row);
        flags.Dock = DockStyle.Fill;
        _advancedTable.Controls.Add(flags, 1, row);
        _advancedTable.Controls.Add(new Label { Text = "", AutoSize = true }, 2, row);

        box.Controls.Add(_advancedTable);
        return box;
    }

    private static TableLayoutPanel NewTable()
    {
        TableLayoutPanel t = new TableLayoutPanel();
        t.AutoSize = false;
        t.ColumnCount = 3;
        t.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 240));
        t.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100F));
        t.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 90));
        t.Margin = new Padding(3);
        t.GrowStyle = TableLayoutPanelGrowStyle.AddRows;
        return t;
    }

    private void AddFileRow(TableLayoutPanel t, string label, TextBox box, bool allowSave, string helpText)
    {
        AddInputRow(t, label, box, helpText, delegate
        {
            if (allowSave)
            {
                SaveFileDialog sfd = new SaveFileDialog();
                sfd.Filter = "CSV (*.csv)|*.csv|Tutti i file (*.*)|*.*";
                sfd.FileName = box.Text;
                if (sfd.ShowDialog(this) == DialogResult.OK)
                {
                    box.Text = sfd.FileName;
                }
            }
            else
            {
                OpenFileDialog ofd = new OpenFileDialog();
                ofd.Filter = "CSV (*.csv)|*.csv|Tutti i file (*.*)|*.*";
                if (File.Exists(box.Text))
                {
                    ofd.FileName = box.Text;
                }
                if (ofd.ShowDialog(this) == DialogResult.OK)
                {
                    box.Text = ofd.FileName;
                }
            }
        });
    }

    private void AddFolderRow(TableLayoutPanel t, string label, TextBox box, string helpText)
    {
        AddInputRow(t, label, box, helpText, delegate
        {
            FolderBrowserDialog fbd = new FolderBrowserDialog();
            if (Directory.Exists(box.Text))
            {
                fbd.SelectedPath = box.Text;
            }
            if (fbd.ShowDialog(this) == DialogResult.OK)
            {
                box.Text = fbd.SelectedPath;
            }
        });
    }

    private void AddPlainRow(TableLayoutPanel t, string label, TextBox box, string hint, string helpText)
    {
        int row = t.RowCount++;
        t.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        t.Controls.Add(CreateLabelWithHelp(label, helpText), 0, row);
        box.Dock = DockStyle.Fill;
        t.Controls.Add(box, 1, row);
        t.Controls.Add(new Label { Text = "", AutoSize = true }, 2, row);
        if (!string.IsNullOrWhiteSpace(hint))
        {
            SetCueBanner(box, hint);
        }
        _toolTip.SetToolTip(box, helpText);
    }

    private void AddNumericRow(TableLayoutPanel t, string label, NumericUpDown num, string helpText)
    {
        int row = t.RowCount++;
        t.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        t.Controls.Add(CreateLabelWithHelp(label, helpText), 0, row);
        num.Width = 120;
        t.Controls.Add(num, 1, row);
        t.Controls.Add(new Label { Text = "", AutoSize = true }, 2, row);
        _toolTip.SetToolTip(num, helpText);
    }

    private void AddInputRow(TableLayoutPanel t, string label, TextBox box, string helpText, Action onBrowse)
    {
        int row = t.RowCount++;
        t.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        t.Controls.Add(CreateLabelWithHelp(label, helpText), 0, row);
        box.Dock = DockStyle.Fill;
        t.Controls.Add(box, 1, row);

        Button btn = new Button();
        btn.Text = "Sfoglia";
        btn.Width = 80;
        btn.Click += delegate { onBrowse(); };
        t.Controls.Add(btn, 2, row);

        _toolTip.SetToolTip(box, helpText);
    }

    private Control CreateLabelWithHelp(string label, string helpText)
    {
        FlowLayoutPanel panel = new FlowLayoutPanel();
        panel.AutoSize = true;
        panel.AutoSizeMode = AutoSizeMode.GrowAndShrink;
        panel.FlowDirection = FlowDirection.LeftToRight;
        panel.WrapContents = false;
        panel.Margin = new Padding(0);
        panel.Padding = new Padding(0);

        Label lbl = new Label();
        lbl.Text = label;
        lbl.AutoSize = true;
        lbl.Anchor = AnchorStyles.Left;
        lbl.Margin = new Padding(3, 8, 3, 3);
        panel.Controls.Add(lbl);

        Button help = new Button();
        help.Text = "?";
        help.Width = 22;
        help.Height = 22;
        help.Margin = new Padding(2, 4, 3, 3);
        help.Click += delegate
        {
            MessageBox.Show(this, helpText, "Spiegazione parametro", MessageBoxButtons.OK, MessageBoxIcon.Information);
        };
        panel.Controls.Add(help);

        _toolTip.SetToolTip(lbl, helpText);
        _toolTip.SetToolTip(help, helpText);
        return panel;
    }

    private void UpdateResponsiveLayout()
    {
        if (_flow == null)
        {
            return;
        }

        int contentWidth = Math.Max(400, _flow.ClientSize.Width - _flow.Padding.Left - _flow.Padding.Right - 24);

        if (_essentialTable != null)
        {
            _essentialTable.Width = contentWidth;
        }

        if (_advancedGroup != null)
        {
            _advancedGroup.Width = contentWidth;
            _advancedGroup.Height = _advancedGroup.PreferredSize.Height;
        }

        if (_advancedTable != null)
        {
            _advancedTable.Width = Math.Max(300, _advancedGroup.ClientSize.Width - _advancedGroup.Padding.Left - _advancedGroup.Padding.Right - 6);
            _advancedTable.Height = _advancedTable.PreferredSize.Height;
        }

        if (_runLine != null)
        {
            _runLine.Width = contentWidth;
        }
    }

    private void UpdateSplitLayout()
    {
        if (_split == null)
        {
            return;
        }

        int preferredLogHeight = 180;
        int availableHeight = _split.ClientSize.Height;
        int maxDistance = availableHeight - _split.Panel2MinSize - _split.SplitterWidth;
        int desiredDistance = availableHeight - preferredLogHeight - _split.SplitterWidth;
        int minDistance = _split.Panel1MinSize;

        if (maxDistance < minDistance)
        {
            maxDistance = minDistance;
        }

        int finalDistance = Math.Max(minDistance, Math.Min(desiredDistance, maxDistance));
        if (finalDistance > 0)
        {
            _split.SplitterDistance = finalDistance;
        }
    }

    private void RunClicked(object sender, EventArgs e)
    {
        string raw = _txtRaw.Text.Trim();
        if (raw.Length == 0 || !File.Exists(raw))
        {
            MessageBox.Show(this, "Seleziona un file Raw CSV valido.", "Input mancante", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        List<string> args = BuildArgs();
        if (args == null)
        {
            return;
        }

        _btnRun.Enabled = false;
        _lblStatus.Text = "In esecuzione...";
        _txtLog.Clear();
        AppendLog("Avvio pipeline...");

        ThreadPool.QueueUserWorkItem(delegate
        {
            int exitCode = ExecutePipeline(args);
            BeginInvoke((Action)delegate
            {
                _btnRun.Enabled = true;
                _lblStatus.Text = exitCode == 0 ? "Completato" : "Terminato con errori";
                AppendLog("Fine esecuzione. Exit code: " + exitCode);
            });
        });
    }

    private List<string> BuildArgs()
    {
        List<string> args = new List<string>();
        args.Add("--raw");
        args.Add(_txtRaw.Text.Trim());

        AddPairIfNotEmpty(args, "--patients", _txtPatients.Text);
        AddPairIfNotEmpty(args, "--output", _txtOutput.Text);
        AddPairIfNotEmpty(args, "--scheme-dir", _txtSchemeDir.Text);
        AddPairIfNotEmpty(args, "--results-dir", _txtResultsDir.Text);
        AddPairIfNotEmpty(args, "--id-prefix", _txtIdPrefix.Text);
        AddPairIfNotEmpty(args, "--id-suffix", _txtIdSuffix.Text);

        string study = NormalizeOptionalInput(_txtStudyId.Text, StudyIdExample);
        if (study.Length > 0)
        {
            string[] ids = SplitTokens(study);
            if (ids.Length > 0)
            {
                args.Add("--study-id");
                args.AddRange(ids);
            }
        }

        string categories = NormalizeOptionalInput(_txtCategories.Text, CategoriesExample);
        if (categories.Length > 0)
        {
            string[] cats = SplitTokens(categories);
            if (cats.Length > 0)
            {
                args.Add("--categories");
                args.AddRange(cats);
            }
        }

        if (_numMinOtRun.Value != 3)
        {
            args.Add("--min-ot-run");
            args.Add(_numMinOtRun.Value.ToString(CultureInfo.InvariantCulture));
        }

        double cnAlpha;
        if (!double.TryParse(_txtCnAlpha.Text.Trim(), NumberStyles.Float, CultureInfo.InvariantCulture, out cnAlpha))
        {
            MessageBox.Show(this, "CN Alpha non valido (usa punto decimale, es: 0.05).", "Valore non valido", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return null;
        }
        if (Math.Abs(cnAlpha - 0.05) > 0.0000001)
        {
            args.Add("--cn-alpha");
            args.Add(cnAlpha.ToString(CultureInfo.InvariantCulture));
        }

        int cnWindow;
        if (!int.TryParse(_txtCnWindow.Text.Trim(), NumberStyles.Integer, CultureInfo.InvariantCulture, out cnWindow) || cnWindow <= 0)
        {
            MessageBox.Show(this, "CN Window non valido (intero > 0).", "Valore non valido", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return null;
        }
        if (cnWindow != 2)
        {
            args.Add("--cn-window");
            args.Add(cnWindow.ToString(CultureInfo.InvariantCulture));
        }

        int cnThreshold;
        if (!int.TryParse(_txtCnThreshold.Text.Trim(), NumberStyles.Integer, CultureInfo.InvariantCulture, out cnThreshold) || cnThreshold <= 0)
        {
            MessageBox.Show(this, "CN Threshold non valido (intero > 0).", "Valore non valido", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return null;
        }
        if (cnThreshold != 2)
        {
            args.Add("--cn-threshold");
            args.Add(cnThreshold.ToString(CultureInfo.InvariantCulture));
        }

        if (_chkInvert.Checked)
        {
            args.Add("--invert");
        }
        if (_chkNoGenderSplits.Checked)
        {
            args.Add("--no-gender-splits");
        }

        return args;
    }

    private int ExecutePipeline(List<string> args)
    {
        string baseDir = AppBaseDir();
        string scriptPath = ResolveScriptPath(baseDir);
        if (scriptPath == null)
        {
            AppendLog("Errore: test.py non trovato.");
            return 1;
        }

        string commandArgs = "-u " + QuoteArg(scriptPath) + " " + string.Join(" ", args.Select(QuoteArg).ToArray());

        int code = RunProcessWithLogs("python", commandArgs, baseDir);
        if (code != int.MinValue)
        {
            return code;
        }

        code = RunProcessWithLogs("py", commandArgs, baseDir);
        if (code != int.MinValue)
        {
            return code;
        }

        AppendLog("Errore: Python non trovato nel PATH.");
        return 9009;
    }

    private int RunProcessWithLogs(string cmd, string args, string workingDir)
    {
        try
        {
            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = cmd;
            psi.Arguments = args;
            psi.WorkingDirectory = workingDir;
            psi.UseShellExecute = false;
            psi.RedirectStandardOutput = true;
            psi.RedirectStandardError = true;
            psi.CreateNoWindow = true;
            psi.EnvironmentVariables["PYTHONUNBUFFERED"] = "1";

            using (Process p = new Process())
            {
                p.StartInfo = psi;
                p.OutputDataReceived += delegate(object sender, DataReceivedEventArgs e)
                {
                    if (e.Data != null)
                    {
                        AppendLog(e.Data);
                    }
                };
                p.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs e)
                {
                    if (e.Data != null)
                    {
                        AppendLog("[ERR] " + e.Data);
                    }
                };

                bool started = p.Start();
                if (!started)
                {
                    return int.MinValue;
                }
                p.BeginOutputReadLine();
                p.BeginErrorReadLine();
                p.WaitForExit();
                return p.ExitCode;
            }
        }
        catch
        {
            return int.MinValue;
        }
    }

    private void AppendLog(string line)
    {
        if (InvokeRequired)
        {
            BeginInvoke((Action<string>)AppendLog, line);
            return;
        }
        _txtLog.AppendText(line + Environment.NewLine);
    }

    private static void AddPairIfNotEmpty(List<string> args, string key, string value)
    {
        string clean = value == null ? "" : value.Trim();
        if (clean.Length > 0)
        {
            args.Add(key);
            args.Add(clean);
        }
    }

    private static string[] SplitTokens(string raw)
    {
        return raw
            .Split(new[] { ' ', ',', ';', '\t', '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries)
            .Where(s => s.Trim().Length > 0)
            .ToArray();
    }

    private static string QuoteArg(string value)
    {
        if (string.IsNullOrEmpty(value))
        {
            return "\"\"";
        }
        if (!value.Any(char.IsWhiteSpace) && !value.Contains("\""))
        {
            return value;
        }
        return "\"" + value.Replace("\"", "\\\"") + "\"";
    }

    private static string ResolveScriptPath(string baseDir)
    {
        string local = Path.Combine(baseDir, "test.py");
        if (File.Exists(local))
        {
            return local;
        }
        string parent = Path.GetFullPath(Path.Combine(baseDir, "..", "test.py"));
        if (File.Exists(parent))
        {
            return parent;
        }
        return null;
    }

    private static string AppBaseDir()
    {
        return Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location) ?? Environment.CurrentDirectory;
    }

    private static string NormalizeOptionalInput(string raw, string exampleText)
    {
        string value = raw == null ? "" : raw.Trim();
        if (value.Length == 0)
        {
            return "";
        }
        if (string.Equals(value, exampleText, StringComparison.OrdinalIgnoreCase))
        {
            return "";
        }
        return value;
    }

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern Int32 SendMessage(IntPtr hWnd, int msg, IntPtr wParam, string lParam);

    private static void SetCueBanner(TextBox box, string cue)
    {
        const int EM_SETCUEBANNER = 0x1501;
        if (box.IsHandleCreated)
        {
            SendMessage(box.Handle, EM_SETCUEBANNER, IntPtr.Zero, cue);
            return;
        }
        box.HandleCreated += delegate
        {
            SendMessage(box.Handle, EM_SETCUEBANNER, IntPtr.Zero, cue);
        };
    }
}
