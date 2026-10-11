import { ChangeDetectionStrategy, Component, computed, input, output, signal } from '@angular/core';
import { AppInfo, SampleInfo } from './models';

@Component({
  selector: 'app-upload-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './upload-panel.html',
  styleUrl: './upload-panel.scss',
})
export class UploadPanel {
  readonly info = input<AppInfo | null>(null);
  readonly samples = input<SampleInfo[]>([]);
  readonly fileChosen = output<File>();
  readonly sampleChosen = output<SampleInfo>();

  protected readonly dragging = signal(false);
  protected readonly localError = signal<string | null>(null);
  protected readonly ttlMinutes = computed(() => Math.max(1, Math.round((this.info()?.document_ttl_s ?? 900) / 60)));

  protected onFiles(files: FileList | null): void {
    const file = files?.item(0);
    if (file) this.accept(file);
  }

  protected onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(true);
  }

  protected onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(false);
    this.onFiles(event.dataTransfer?.files ?? null);
  }

  /** Cheap checks here save a round trip; the server repeats them, because it must not trust the browser. */
  private accept(file: File): void {
    const maxBytes = (this.info()?.max_upload_mb ?? 10) * 1024 * 1024;
    const looksLikePdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
    if (!looksLikePdf) {
      this.localError.set('Only PDF files are supported.');
    } else if (file.size > maxBytes) {
      this.localError.set(`The file is larger than ${this.info()?.max_upload_mb ?? 10} MB.`);
    } else {
      this.localError.set(null);
      this.fileChosen.emit(file);
    }
  }
}
