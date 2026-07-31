/**
 * Root loading state.
 *
 * Required by [[Chapter 05 - NextJS Architecture]] §5.9: every route defines
 * loading, error and not-found states. Design System skeletons arrive in
 * STEP-14; this is the minimum honest placeholder until then.
 */
export default function Loading() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      <p className="text-sm opacity-70" role="status">
        Loading…
      </p>
    </main>
  );
}
