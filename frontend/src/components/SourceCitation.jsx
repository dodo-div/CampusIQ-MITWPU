
import { FileText, ExternalLink } from "lucide-react";
import "./SourceCitation.css";

const API_URL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

const DOCUMENTS = {
  "Academic-Calendar-2026-27.txt": {
    filename: "Academic-Calendar-2026-27.pdf",
    title: "Academic Calendar 2026–27",
  },
  "Examination-Ordinance-2022.txt": {
    filename: "Examination-Ordinance-2022.pdf",
    title: "Examination Ordinance 2022",
  },
  "Examination_Ordinances_2020.txt": {
    filename: "Examination_Ordinances_2020.pdf",
    title: "Examination Ordinance 2020",
  },
};

export default function SourceCitation({ citations = [] }) {
  if (!citations.length) return null;

  const unique = citations.filter(
    (citation, index, all) =>
      all.findIndex(
        (item) =>
          item.document === citation.document &&
          item.page === citation.page
      ) === index
  );

  return (
    <div className="source-citations">
      <span className="source-citations-label">Sources</span>

      <div className="source-citations-list">
        {unique.map((citation, index) => {
          const document = DOCUMENTS[citation.document];
          if (!document) return null;

          const page = Number(citation.page);
          const validPage = Number.isInteger(page) && page > 0;

          const url =
            `${API_URL}/api/documents/` +
            encodeURIComponent(document.filename) +
            (validPage ? `#page=${page}` : "");

          return (
            <a
              key={`${citation.document}-${citation.page}-${index}`}
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="source-citation-link"
              title={`Open ${document.title}${validPage ? ` at page ${page}` : ""}`}
            >
              <FileText size={14} />

              <span>
                {document.title}
                {validPage ? ` · Page ${page}` : ""}
              </span>

              <ExternalLink size={13} />
            </a>
          );
        })}
      </div>
    </div>
  );
}
