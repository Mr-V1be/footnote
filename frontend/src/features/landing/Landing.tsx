import { MarketingShell } from "./MarketingShell";
import { Capabilities } from "./sections/Capabilities";
import { FinalCta } from "./sections/FinalCta";
import { Hero } from "./sections/Hero";
import { Numbers } from "./sections/Numbers";
import { Pricing } from "./sections/Pricing";
import { Showcase } from "./sections/Showcase";
import { Steps } from "./sections/Steps";
import { publicFacts } from "./data";
import { mostChecksPerDocument } from "./facts";

/** The product's page for guests: screens of the product, honest numbers, plans. */
export async function Landing() {
  const facts = await publicFacts();
  return (
    <MarketingShell demo={facts.demo}>
      <Hero demo={facts.demo} checks={facts.checks ? mostChecksPerDocument(facts.checks) : null} />
      <Steps />
      <Showcase />
      <Numbers checks={facts.checks} quality={facts.quality} />
      <Capabilities />
      <Pricing plans={facts.plans} demo={facts.demo} />
      <FinalCta demo={facts.demo} />
    </MarketingShell>
  );
}
