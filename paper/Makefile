PAPER = main
LATEX = pdflatex
BIBTEX = bibtex

.PHONY: all clean

all: $(PAPER).pdf

$(PAPER).pdf: $(PAPER).tex references.bib sections/*.tex
	$(LATEX) $(PAPER)
	$(BIBTEX) $(PAPER)
	$(LATEX) $(PAPER)
	$(LATEX) $(PAPER)

clean:
	rm -f $(PAPER).pdf $(PAPER).aux $(PAPER).bbl $(PAPER).blg \
	      $(PAPER).log $(PAPER).out $(PAPER).fls $(PAPER).fdb_latexmk \
	      $(PAPER).synctex.gz
