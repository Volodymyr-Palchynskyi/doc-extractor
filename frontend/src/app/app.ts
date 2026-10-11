import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { ApiClient } from './api-client';
import { AppInfo, SampleInfo } from './models';
import { PageViewer } from './page-viewer';
import { ReviewPanel } from './review-panel';
import { ReviewStore } from './review-store';
import { UploadPanel } from './upload-panel';

type Stage = 'idle' | 'processing' | 'review';

@Component({
  selector: 'app-root',
  imports: [UploadPanel, PageViewer, ReviewPanel],
  providers: [ReviewStore],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App implements OnInit {
  private readonly api = inject(ApiClient);
  protected readonly store = inject(ReviewStore);

  protected readonly stage = signal<Stage>('idle');
  protected readonly info = signal<AppInfo | null>(null);
  protected readonly samples = signal<SampleInfo[]>([]);
  protected readonly error = signal<string | null>(null);
  protected readonly fileName = signal('');

  private abort: AbortController | null = null;

  async ngOnInit(): Promise<void> {
    // Info and samples only decorate the screen, so a failure is reported but does not block uploading.
    const [info, samples] = await Promise.allSettled([this.api.info(), this.api.samples()]);
    if (info.status === 'fulfilled') this.info.set(info.value);
    if (samples.status === 'fulfilled') this.samples.set(samples.value);
    const failure = [info, samples].find((r) => r.status === 'rejected');
    if (failure?.status === 'rejected') this.error.set(failure.reason instanceof Error ? failure.reason.message : 'Cannot reach the server.');
  }

  protected async process(file: Blob, name: string): Promise<void> {
    this.error.set(null);
    this.fileName.set(name);
    this.stage.set('processing');
    const controller = new AbortController();
    this.abort = controller;
    try {
      this.store.load(await this.api.extract(file, name, controller.signal));
      this.stage.set('review');
    } catch (error) {
      this.stage.set('idle');
      if (!controller.signal.aborted) this.error.set(error instanceof Error ? error.message : 'Something went wrong.');
    } finally {
      if (this.abort === controller) this.abort = null;
    }
  }

  protected async useSample(sample: SampleInfo): Promise<void> {
    this.error.set(null);
    this.fileName.set(sample.file_name);
    this.stage.set('processing');
    try {
      await this.process(await this.api.samplePdf(sample.id), sample.file_name);
    } catch (error) {
      this.stage.set('idle');
      this.error.set(error instanceof Error ? error.message : 'Could not load the sample.');
    }
  }

  protected cancel(): void {
    this.abort?.abort();
  }

  protected newDocument(): void {
    const id = this.store.result()?.document_id;
    this.store.reset();
    this.stage.set('idle');
    this.error.set(null);
    if (id) void this.api.deleteDocument(id); // free the server's copy now instead of waiting for the TTL
  }
}
