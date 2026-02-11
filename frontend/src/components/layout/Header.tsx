export function Header() {
  return (
    <header className="sticky top-0 z-40 flex items-center h-16 px-6 bg-card/80 backdrop-blur-sm border-b lg:pl-64">
      <div className="flex items-center justify-between w-full">
        <div className="lg:hidden">
          <h1 className="text-lg font-bold">
            <span className="text-primary">Japan</span> REIT
          </h1>
        </div>
        <div className="flex items-center gap-4 ml-auto">
          <span className="text-sm text-muted-foreground">
            Japanese Real Estate Investment Tool
          </span>
        </div>
      </div>
    </header>
  )
}
