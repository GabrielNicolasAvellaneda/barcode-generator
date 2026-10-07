import qrcode
import numpy as np
import svgwrite

def generate_dot_qr_svg(data, filename="dot_qr.svg", size=10, border=4):
    """
    Generates a QR code with circular dots and saves it as an SVG file.

    Parameters:
        data (str): The data to encode in the QR code.
        filename (str): The filename to save the QR code image.
        size (int): Size of each dot.
        border (int): Border size for QR code.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)

    # Convert QR code to numpy array
    qr_matrix = np.array(qr.make_image(fill_color="black", back_color="white"))

    # Calculate the size of the SVG canvas
    qr_size = qr_matrix.shape[0] * size
    dwg = svgwrite.Drawing(filename, size=(qr_size, qr_size))

    # Draw dots for each black module
    for y in range(qr_matrix.shape[0]):
        for x in range(qr_matrix.shape[1]):
            if qr_matrix[y, x]:  # If black (part of the QR code)
                dwg.add(dwg.circle(
                    center=(x * size + size / 2, y * size + size / 2),
                    r=size / 3,  # Adjust dot radius
                    fill="black"
                ))

    # Save the SVG file
    dwg.save()
    print(f"SVG QR Code saved as {filename}")

# Example usage
generate_dot_qr_svg("https://www.bloxi.com.br", "bloxi_qr.svg")
