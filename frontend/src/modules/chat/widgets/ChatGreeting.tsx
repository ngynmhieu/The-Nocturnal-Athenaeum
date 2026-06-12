export function ChatGreeting() {
  return (
    <div className="flex flex-col items-center gap-6">
      <img
        src="./src/shared/assets/owl_teaching_with_glasses.png"
        alt="The Nocturnal Athenaeum mascot"
        className="w-64 h-64 object-contain drop-shadow-lg"
      />
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-semibold text-[var(--owl-brown-deep)] tracking-tight">
          The Docent
        </h1>
        <p className="text-[var(--owl-brown)] text-base opacity-80">
          Your guide through knowledge, one question at a time.
        </p>
      </div>
    </div>
  );
}
