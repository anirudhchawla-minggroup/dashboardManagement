from django import forms

# Custom MultipleFileInput that allows selecting multiple files
class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

# Custom MultipleFileField to handle multiple file uploads
class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result

# Update the form to allow multiple PDF file uploads
class PDFUploadForm(forms.Form):
    pdf_files = MultipleFileField(
        label='Select PDF files',
        required=True  # You can change this to False if files are optional
    )
