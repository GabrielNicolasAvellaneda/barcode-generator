#!/usr/bin/env python3
import argparse
import io
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import qrcode
from barcode import EAN13
from barcode.writer import SVGWriter
from qrcode.image.svg import SvgPathImage

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
TEMPLATE_FILENAME = "bloxi-barcode-template.svg"

BARCODE_OPTIONS = {
    'module_height': 12.0,
    'text_distance': 3,
    'quiet_zone': 0,
    'background': 'white',
    'write_text': False,
}

ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)


def qname(tag):
    return f"{{{SVG_NS}}}{tag}"


def parse_mm(value):
    return float(value.removesuffix("mm"))


def format_number(value):
    formatted = f"{value:.2f}".rstrip("0").rstrip(".")
    if formatted.startswith("0."):
        return formatted[1:]
    if formatted.startswith("-0."):
        return "-" + formatted[2:]
    return formatted


def build_plain_barcode_root(code):
    barcode_svg = EAN13(code, writer=SVGWriter())
    svg_data = io.BytesIO()
    barcode_svg.write(svg_data, BARCODE_OPTIONS)
    return ET.fromstring(svg_data.getvalue())


def get_plain_bar_rects(plain_root):
    barcode_group = plain_root.find(f".//{qname('g')}[@id='barcode_group']")
    if barcode_group is None:
        raise ValueError("Generated SVG does not contain barcode_group.")

    bar_rects = []
    for rect in barcode_group.findall(qname("rect")):
        style = rect.attrib.get("style", "")
        if rect.attrib.get("x") is None or "fill:black" not in style:
            continue
        bar_rects.append(rect)

    if not bar_rects:
        raise ValueError("Generated SVG does not contain barcode bars.")

    return bar_rects


def get_template_metrics(barcode_group):
    background = None
    template_bars = []

    for rect in barcode_group.findall(qname("rect")):
        if rect.attrib.get("class") == "cls-1":
            background = dict(rect.attrib)
        else:
            template_bars.append(rect)

    if background is None:
        raise ValueError("Template barcode group does not contain a background rect.")
    if not template_bars:
        raise ValueError("Template barcode group does not contain sample bars.")

    min_x = min(float(rect.attrib.get("x", "0")) for rect in template_bars)
    max_x = max(
        float(rect.attrib.get("x", "0")) + float(rect.attrib["width"])
        for rect in template_bars
    )
    first_bar = template_bars[0]

    return {
        "background": background,
        "x": min_x,
        "width": max_x - min_x,
        "bar_y": first_bar.attrib["y"],
        "bar_height": first_bar.attrib["height"],
    }


def generate_ean13_template_svg(code):
    template_path = Path(__file__).resolve().with_name(TEMPLATE_FILENAME)
    tree = ET.parse(template_path)
    root = tree.getroot()
    barcode_group = root.find(f".//{qname('g')}[@id='Codigo_de_Barras']")
    if barcode_group is None:
        raise ValueError(f"{TEMPLATE_FILENAME} does not contain Codigo_de_Barras.")

    metrics = get_template_metrics(barcode_group)
    plain_root = build_plain_barcode_root(code)
    plain_width = parse_mm(plain_root.attrib["width"])
    scale = metrics["width"] / plain_width

    barcode_group.clear()
    barcode_group.set("id", "Codigo_de_Barras")
    barcode_group.set("data-name", "Codigo de Barras")
    barcode_group.append(ET.Element(qname("rect"), metrics["background"]))

    for plain_rect in get_plain_bar_rects(plain_root):
        x = metrics["x"] + parse_mm(plain_rect.attrib["x"]) * scale
        width = parse_mm(plain_rect.attrib["width"]) * scale
        barcode_group.append(
            ET.Element(
                qname("rect"),
                {
                    "x": format_number(x),
                    "y": metrics["bar_y"],
                    "width": format_number(width),
                    "height": metrics["bar_height"],
                },
            )
        )

    filename = f"bloxi-{code}.svg"
    tree.write(filename, encoding="UTF-8", xml_declaration=True)
    print(f"Barcode saved as: {filename}")


def generate_ean13_plain_svg(code):
    """
    Generate an EAN-13 barcode as an SVG file.
    The file is saved as <code>.svg.
    """
    barcode_svg = EAN13(code, writer=SVGWriter())
    filename = barcode_svg.save(code, BARCODE_OPTIONS)
    print(f"Barcode saved as: {filename}")


def generate_qr_svg(content, product_code):
    """Generate a standard QR code containing the input line as an SVG file."""
    filename = f"qr_{product_code}.svg"
    image = qrcode.make(content, image_factory=SvgPathImage)
    image.save(filename)
    print(f"QR code saved as: {filename}")


def parse_qr_content(line):
    """Return the product code from a ``product_code:quantity`` input line."""
    product_code, separator, quantity = line.partition(":")
    if not separator or not product_code or not quantity:
        raise ValueError("must use the product_code:quantity format")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", product_code):
        raise ValueError("product code contains characters that are unsafe in a filename")
    return product_code


def main():
    parser = argparse.ArgumentParser(
        description="Generate EAN-13 barcode or QR code SVGs from stdin."
    )
    output_mode = parser.add_mutually_exclusive_group()
    output_mode.add_argument(
        "--plain",
        action="store_true",
        help="Generate the plain python-barcode SVG instead of using the Bloxi template.",
    )
    output_mode.add_argument(
        "--qr",
        action="store_true",
        help="Generate a QR code for each product_code:quantity input line.",
    )
    args = parser.parse_args()

    # Read from standard input
    if args.qr:
        prompt = "Enter product_code:quantity values"
    else:
        prompt = "Enter 13-digit barcodes"
    print(f"{prompt} (one per line). Press Ctrl+D (or Ctrl+Z on Windows) to finish input:")
    input_lines = sys.stdin.read().splitlines()

    if not input_lines:
        print("No input received.")
        sys.exit(1)

    for line in input_lines:
        code = line.strip()
        if not code:
            continue  # Skip empty lines
        if args.qr:
            try:
                product_code = parse_qr_content(code)
            except ValueError as error:
                print(f"Skipping invalid QR content: {code} ({error})")
                continue
            generate_qr_svg(code, product_code)
            continue
        if not (code.isdigit() and len(code) == 13):
            print(f"Skipping invalid barcode: {code} (must be a 13-digit number)")
            continue
        if args.plain:
            generate_ean13_plain_svg(code)
        else:
            generate_ean13_template_svg(code)

if __name__ == '__main__':
    main()
