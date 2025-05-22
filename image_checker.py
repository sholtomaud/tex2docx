from PIL import Image

def check_image(image_path):
    print(f"Investigating {image_path}...")
    try:
        img = Image.open(image_path)
        print(f"  Successfully opened with Pillow.")
        try:
            img.verify()
            print(f"  Image.verify() successful.")
            print(f"  Pillow format: {img.format}")
        except Exception as e_verify:
            print(f"  Error during Image.verify(): {type(e_verify).__name__} - {e_verify}")
        img.close() # Close the image after verify, as verify can make it unusable
        
        # Re-open for format check if verify was successful, as verify() might invalidate the image object for some formats
        # or make it unable to report format correctly.
        # For text files identified as images, open() might succeed but format might be None.
        if img.format is None: # Check if format was None after initial open and verify
            try:
                img_reopened = Image.open(image_path)
                print(f"  Re-opened. Pillow format (after re-open): {img_reopened.format}")
                img_reopened.close()
            except Exception as e_reopen:
                 print(f"  Could not re-open to check format: {type(e_reopen).__name__} - {e_reopen}")

    except Exception as e_open:
        print(f"  Error opening image with Pillow: {type(e_open).__name__} - {e_open}")
    print("-" * 30)

if __name__ == "__main__":
    image_paths = ["images/sample_image.png", "images/another_image.jpeg"]
    for path in image_paths:
        check_image(path)
