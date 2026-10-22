param(
    [Parameter(Mandatory = $true)]
    [string]$InputRoot,
    [Parameter(Mandatory = $true)]
    [string]$OutputRoot
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing
$drawingAssembly = [System.Drawing.Bitmap].Assembly.Location
$drawingDirectory = Split-Path -Parent $drawingAssembly
$drawingReferences = @(
    Get-ChildItem -LiteralPath $drawingDirectory -Filter "System.Drawing*.dll" -File
    Get-ChildItem -LiteralPath $drawingDirectory -Filter "System.Private.Windows*.dll" -File
) | Select-Object -ExpandProperty FullName -Unique

Add-Type -TypeDefinition @"
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;

public static class EdgeDespill
{
    public static void Process(string input, string output)
    {
        using (var source = new Bitmap(input))
        using (var bitmap = new Bitmap(
            source.Width, source.Height, PixelFormat.Format32bppArgb))
        {
            using (var graphics = Graphics.FromImage(bitmap))
            {
                graphics.DrawImageUnscaled(source, 0, 0);
            }

            int width = bitmap.Width;
            int height = bitmap.Height;
            int stride = width * 4;
            byte[] bytes = new byte[stride * height];
            var rect = new Rectangle(0, 0, width, height);
            var data = bitmap.LockBits(
                rect, ImageLockMode.ReadWrite, PixelFormat.Format32bppArgb);
            try
            {
                Marshal.Copy(data.Scan0, bytes, 0, bytes.Length);

                bool IsChroma(int offset)
                {
                    return bytes[offset] < 4
                        && bytes[offset + 1] > 251
                        && bytes[offset + 2] < 4;
                }

                bool backgroundMode = IsChroma(0)
                    && IsChroma((width - 1) * 4)
                    && IsChroma((height - 1) * stride)
                    && IsChroma((height - 1) * stride + (width - 1) * 4);

                bool IsActive(int offset)
                {
                    if (backgroundMode) return !IsChroma(offset);
                    return bytes[offset + 3] > 8;
                }

                for (int y = 0; y < height; y++)
                {
                    int row = y * stride;
                    for (int x = 0; x < width; x++)
                    {
                        int i = row + x * 4;
                        if (!IsActive(i)) continue;

                        int alpha = bytes[i + 3];
                        bool edge = !backgroundMode && alpha < 250;
                        if (!edge)
                        {
                            edge =
                                (x == 0 || !IsActive(i - 4))
                                || (x + 1 == width || !IsActive(i + 4))
                                || (y == 0 || !IsActive(i - stride))
                                || (y + 1 == height || !IsActive(i + stride));
                        }
                        if (!edge) continue;

                        int b = bytes[i];
                        int g = bytes[i + 1];
                        int r = bytes[i + 2];
                        int spill = g - Math.Max(r, b);
                        if (spill <= 2) continue;

                        bytes[i + 1] = (byte)Math.Max(r, b);
                    }
                }

                Marshal.Copy(bytes, 0, data.Scan0, bytes.Length);
            }
            finally
            {
                bitmap.UnlockBits(data);
            }

            var parent = System.IO.Path.GetDirectoryName(output);
            if (!System.IO.Directory.Exists(parent))
            {
                System.IO.Directory.CreateDirectory(parent);
            }
            bitmap.Save(output, ImageFormat.Png);
        }
    }
}
"@ -ReferencedAssemblies $drawingReferences

$input = (Resolve-Path -LiteralPath $InputRoot).Path
$output = [System.IO.Path]::GetFullPath($OutputRoot)
if (Test-Path -LiteralPath $output) {
    throw "OutputRoot already exists: $output"
}
New-Item -ItemType Directory -Path $output | Out-Null

foreach ($directory in Get-ChildItem -LiteralPath $input -Directory | Sort-Object Name) {
    $destinationDirectory = Join-Path $output $directory.Name
    New-Item -ItemType Directory -Path $destinationDirectory | Out-Null
    foreach ($file in Get-ChildItem -LiteralPath $directory.FullName -Filter "*.png" -File |
        Sort-Object Name) {
        [EdgeDespill]::Process(
            $file.FullName,
            (Join-Path $destinationDirectory $file.Name)
        )
    }
    Write-Output ("{0,-25} processed" -f $directory.Name)
}
