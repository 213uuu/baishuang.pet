using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Windows.Forms;

[assembly: AssemblyTitle("Baishuang Setup")]
[assembly: AssemblyDescription("Baishuang desktop pet installer")]
[assembly: AssemblyCompany("213uuu")]
[assembly: AssemblyProduct("Baishuang")]
[assembly: AssemblyVersion("0.1.8.0")]
[assembly: AssemblyFileVersion("0.1.8.0")]

internal static class Program
{
    private const string PayloadResource = "payload.zip";

    [STAThread]
    private static void Main(string[] args)
    {
        bool silent = HasArgument(args, "--silent");
        bool noLaunch = HasArgument(args, "--no-launch");
        string installDirOverride = GetOptionValue(args, "--install-dir");
        try
        {
            if (!silent)
            {
                DialogResult answer = MessageBox.Show(
                    "Install Baishuang for the current Windows user?\n\n" +
                    "No administrator rights are required.",
                    "Baishuang Setup",
                    MessageBoxButtons.OKCancel,
                    MessageBoxIcon.Information);
                if (answer != DialogResult.OK) return;
            }

            string work = Path.Combine(
                Path.GetTempPath(),
                "BaishuangSetup-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(work);
            try
            {
                string archive = Path.Combine(work, "payload.zip");
                using (Stream resource = Assembly.GetExecutingAssembly()
                    .GetManifestResourceStream(PayloadResource))
                using (FileStream output = File.Create(archive))
                {
                    if (resource == null)
                    {
                        throw new InvalidDataException("Embedded payload is missing.");
                    }
                    resource.CopyTo(output);
                }

                ZipFile.ExtractToDirectory(archive, work);
                string target = installDirOverride ?? Path.Combine(
                    Environment.GetFolderPath(
                        Environment.SpecialFolder.LocalApplicationData),
                    "Baishuang");
                target = Path.GetFullPath(target);
                Directory.CreateDirectory(target);
                CopyDirectory(work, target, "payload.zip");

                RunPowerShell(Path.Combine(target, "install.ps1"), target);
                if (!silent)
                {
                    MessageBox.Show(
                        "Baishuang was installed successfully.\n\n" + target,
                        "Baishuang Setup",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Information);
                }
                if (!noLaunch)
                {
                    Process.Start(new ProcessStartInfo
                    {
                        FileName = Path.Combine(target, "start-pet.cmd"),
                        WorkingDirectory = target,
                        UseShellExecute = true,
                        WindowStyle = ProcessWindowStyle.Minimized
                    });
                }
            }
            finally
            {
                try { Directory.Delete(work, true); } catch { }
            }
        }
        catch (Exception error)
        {
            try
            {
                File.WriteAllText(
                    Path.Combine(Path.GetTempPath(), "BaishuangSetup-error.log"),
                    error.ToString());
            }
            catch { }
            if (!silent)
            {
                MessageBox.Show(
                    "Installation failed:\n\n" + error.Message,
                    "Baishuang Setup",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error);
            }
            Environment.ExitCode = 1;
        }
    }

    private static bool HasArgument(string[] args, string expected)
    {
        foreach (string arg in args)
        {
            if (string.Equals(arg, expected, StringComparison.OrdinalIgnoreCase))
                return true;
        }
        return false;
    }

    private static string GetOptionValue(string[] args, string option)
    {
        for (int index = 0; index < args.Length; index++)
        {
            if (string.Equals(
                args[index], option, StringComparison.OrdinalIgnoreCase))
            {
                if (index + 1 < args.Length) return args[index + 1];
                return null;
            }
            string prefix = option + "=";
            if (args[index].StartsWith(
                prefix, StringComparison.OrdinalIgnoreCase))
            {
                return args[index].Substring(prefix.Length);
            }
        }
        return null;
    }

    private static void CopyDirectory(
        string source,
        string destination,
        string skipFileName)
    {
        foreach (string directory in Directory.GetDirectories(
            source, "*", SearchOption.AllDirectories))
        {
            Directory.CreateDirectory(Path.Combine(
                destination,
                directory.Substring(source.Length).TrimStart(
                    Path.DirectorySeparatorChar)));
        }
        foreach (string file in Directory.GetFiles(
            source, "*", SearchOption.AllDirectories))
        {
            if (string.Equals(
                Path.GetFileName(file), skipFileName,
                StringComparison.OrdinalIgnoreCase)) continue;
            string target = Path.Combine(
                destination,
                file.Substring(source.Length).TrimStart(
                    Path.DirectorySeparatorChar));
            Directory.CreateDirectory(Path.GetDirectoryName(target));
            using (FileStream input = File.OpenRead(file))
            using (FileStream output = File.Create(target))
            {
                input.CopyTo(output);
            }
        }
    }

    private static void RunPowerShell(string scriptPath, string installDir)
    {
        ProcessStartInfo startInfo = new ProcessStartInfo
        {
            FileName = "powershell.exe",
            Arguments = "-NoProfile -ExecutionPolicy Bypass -File \"" +
                scriptPath + "\" -InstallDir \"" + installDir + "\"",
            UseShellExecute = false,
            CreateNoWindow = true,
            WindowStyle = ProcessWindowStyle.Hidden
        };
        using (Process process = Process.Start(startInfo))
        {
            process.WaitForExit();
            if (process.ExitCode != 0)
            {
                throw new InvalidOperationException(
                    "Installer configuration failed with exit code " +
                    process.ExitCode + ".");
            }
        }
    }
}
