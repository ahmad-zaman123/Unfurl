/** A card shown as a press proof: crop marks at the corners, a registration cross above. */
export default function Proof({ children, className = "", caption }) {
  return (
    <figure className={"proof " + className} style={{ margin: 0 }}>
      <i className="crop tl" aria-hidden="true" />
      <i className="crop tr" aria-hidden="true" />
      <i className="crop bl" aria-hidden="true" />
      <i className="crop br" aria-hidden="true" />
      <svg className="proof-reg" width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
        <circle cx="7" cy="7" r="4.2" stroke="currentColor" strokeWidth="1" />
        <path d="M7 0v14M0 7h14" stroke="currentColor" strokeWidth="1" />
      </svg>
      {children}
      {caption && (
        <figcaption className="proof-caption">
          {caption}
          <span className="colorbar" aria-hidden="true">
            <i />
            <i />
            <i />
            <i />
          </span>
        </figcaption>
      )}
    </figure>
  );
}
