from django.core.files.uploadhandler import FileUploadHandler, StopUpload

MAX_TAMANHO_BYTES = 20 * 1024 * 1024


class LimiteUploadHandler(FileUploadHandler):
    """Interrompe uploads que ultrapassam 20 MiB."""

    def new_file(self, *args, **kwargs):
        super().new_file(*args, **kwargs)
        self.bytes_recebidos = 0

    def receive_data_chunk(self, raw_data, start):
        self.bytes_recebidos += len(raw_data)

        if self.bytes_recebidos > MAX_TAMANHO_BYTES:
            self.request.upload_excedeu_limite = True
            raise StopUpload(connection_reset=False)

        return raw_data

    def file_complete(self, file_size):
        return None