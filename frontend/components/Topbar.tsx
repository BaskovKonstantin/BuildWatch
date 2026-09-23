export function Topbar({
  crumbs,
  chips,
  action,
}: {
  crumbs: React.ReactNode;
  chips?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="topbar">
      <div className="brand">
        <span className="logo">B</span>
        <span>
          BuildWatch
          <small>монитор стройконтроля</small>
        </span>
      </div>
      <div className="crumbs">{crumbs}</div>
      <div className="spacer" />
      {chips}
      {action}
    </div>
  );
}
