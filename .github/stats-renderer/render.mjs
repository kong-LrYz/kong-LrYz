import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { calculateRank } from "./node_modules/@stats-organization/github-readme-stats-core/build/calculateRank.js";
import { renderStatsCard } from "./node_modules/@stats-organization/github-readme-stats-core/build/cards/stats.js";

const [publicPath, totalsPath, outputDir] = process.argv.slice(2);
const profile = JSON.parse(await readFile(publicPath, "utf8"));
const totals = JSON.parse(await readFile(totalsPath, "utf8"));

for (const count of [totals.commits, totals.prs]) {
  if (!Number.isSafeInteger(count) || count < 0) {
    throw new Error("Invalid account totals");
  }
}

const stats = {
  name: profile.name || profile.login,
  totalStars: profile.repositories.nodes.reduce((sum, repo) => sum + repo.stargazerCount, 0),
  totalCommits: totals.commits,
  totalPRs: totals.prs,
  totalIssues: profile.issues.totalCount,
  totalReviews: profile.contributionsCollection.totalPullRequestReviewContributions,
  contributedTo: profile.repositoriesContributedTo.totalCount,
};

stats.rank = calculateRank({
  all_commits: true,
  commits: stats.totalCommits,
  prs: stats.totalPRs,
  reviews: stats.totalReviews,
  issues: stats.totalIssues,
  repos: profile.repositories.totalCount,
  stars: stats.totalStars,
  followers: profile.followers.totalCount,
});

for (const [mode, theme] of Object.entries({ light: "default", dark: "github_dark" })) {
  const svg = renderStatsCard(stats, {
    show_icons: true,
    include_all_commits: true,
    hide_border: true,
    number_format: "long",
    theme,
    bg_color: "00000000",
  }, profile.login);
  await writeFile(join(outputDir, `github-stats-${mode}.svg`), svg, "utf8");
}
