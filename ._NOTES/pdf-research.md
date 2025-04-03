## recommendation

- Docling
- PyMuPDF4LLM – good for non-scanned PDFs
- Markitdown – low quality

## notes

[Marker](https://github.com/VikParuchuri/marker) - random person – Under the Hood: Underneath, Marker uses PyMuPDF for parsing PDF text and layout, combined with Tesseract OCR for any text that’s embedded in images or scans ￼. This hybrid approach means purely digital-text PDFs are handled via PDF parsing, while scanned pages are OCR’d – ensuring no text is missed. (It can automatically fall back to OCR or be forced via a flag.) The design prioritizes efficiency and can utilize GPU acceleration for OCR (via the Surya OCR toolkit) if available ￼, though it runs on CPU as well. The dependency footprint is relatively lightweight: installable via pip (pip install marker-pdf) with no external system libraries required, aside from having Tesseract available for OCR (optional) ￼.

Limitations: Because Marker is optimized for speed and common layouts, extremely complex multi-column arrangements or very intricate tables might not be perfectly formatted in Markdown. For instance, tables with complicated cell structures might sometimes come out slightly misaligned in Markdown form ￼. Similarly, math formulas that are very complex might be captured as images or have limited accuracy in conversion ￼ unless the optional LLM post-processor is used. However, for the vast majority of PDFs, Marker offers an excellent balance of quality and simplicity. It supports embedded links and reference citations as plain Markdown hyperlinks.

Sources suggest that Marker’s performance is competitive with even cloud-based services, and it has the advantage of being entirely local ￼. With an easy pip install and broad format support (it also can handle DOCX, PPTX, images, etc., when extra dependencies are installed), Marker is a top choice for an all-around PDF-to-Markdown converter.

[MinerU](https://github.com/opendatalab/MinerU) - Chinese opendatalab – might be higher quality, uses pipeline of models. Requires model weights and has large footprint. But it's all done using Python ML stack (no external system libs like Poppler or ImageMagick), but GPU is necessary for fast performance. Probably best in class for open-source, but it's slow.

[Docling](https://github.com/docling-project/docling) – IBM - optimized for producing content for LMs and documentation. no cloud services. under the hood uses parts of unstructured, layoutparser. but you don't have to manually install things like poppler or tesseract? Saves images into the markdown. Planned metadata extraction but noted as coming soon...

## future

- for pdf parsing, consider https://arxiv.org/pdf/2503.11576 – SmolDocling, newer VLM research
- https://www.aryn.ai – newer player, ml model, maybe better at complex docs
